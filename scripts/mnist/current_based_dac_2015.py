import os
import sys
import torch
import argparse
import numpy as np
import pickle as p
import matplotlib.pyplot as plt

from bindsnet import *
from time     import time as t

parser = argparse.ArgumentParser()
parser.add_argument('--seed', type=int, default=0)
parser.add_argument('--n_neurons', type=int, default=100)
parser.add_argument('--n_train', type=int, default=60000)
parser.add_argument('--n_test', type=int, default=10000)
parser.add_argument('--excite', type=float, default=17.5)
parser.add_argument('--inhib', type=float, default=17.5)
parser.add_argument('--time', type=int, default=350)
parser.add_argument('--dt', type=float, default=0.5)
parser.add_argument('--theta_plus', type=float, default=0.05)
parser.add_argument('--theta_decay', type=float, default=1e-7)
parser.add_argument('--intensity', type=float, default=0.25)
parser.add_argument('--progress_interval', type=int, default=10)
parser.add_argument('--update_interval', type=int, default=250)
parser.add_argument('--train', dest='train', action='store_true')
parser.add_argument('--test', dest='train', action='store_false')
parser.add_argument('--plot', dest='plot', action='store_true')
parser.add_argument('--gpu', dest='gpu', action='store_true')
parser.set_defaults(plot=False, gpu=False, train=True)

args = vars(parser.parse_args())
locals().update(args)

print(); print('Command-line argument values:')
for key, value in args.items():
    print('-', key, ':', value)

print()

assert n_train % update_interval == 0 and n_test % update_interval == 0, \
                        'No. examples must be divisible by update_interval'

params = [seed, n_neurons, n_train, excite,
          inhib, time, dt, theta_plus, theta_decay,
          intensity, progress_interval, update_interval]

model_name = '_'.join([str(x) for x in params])

if not train:
    test_params = [seed, n_neurons, n_train, n_test, excite,
                   inhib, time, dt, theta_plus, theta_decay,
                   intensity, progress_interval, update_interval]

np.random.seed(seed)

if gpu:
    torch.set_default_tensor_type('torch.cuda.FloatTensor')
    torch.cuda.manual_seed_all(seed)
else:
    torch.manual_seed(seed)

if train:
    n_examples = n_train
else:
    n_examples = n_test

n_sqrt = int(np.ceil(np.sqrt(n_neurons)))
start_intensity = intensity
    
# Build network.
if train:
    network = DiehlAndCook2015(n_inpt=784,
                               n_neurons=n_neurons,
                               exc=excite,
                               inh=inhib,
                               dt=dt,
                               norm=78.4,
                               theta_plus=1)

    network.layers['Ae'] = AdaptiveCurrentLIFNodes(n=n_neurons,
                                                   traces=True,
                                                   rest=-65.0,
                                                   reset=-60.0,
                                                   thresh=-52.0,
                                                   refrac=5,
                                                   decay=1e-2,
                                                   i_decay=5e-1,
                                                   trace_tc=5e-2,
                                                   theta_plus=theta_plus,
                                                   theta_decay=theta_decay)

    network.layers['Ai'] = CurrentLIFNodes(n=n_neurons,
                                           traces=False,
                                           rest=-60.0,
                                           reset=-45.0,
                                           thresh=-40.0,
                                           decay=1e-1,
                                           i_decay=5e-1,
                                           refrac=2,
                                           trace_tc=5e-2)

    network.connections[('X', 'Ae')] = Connection(source=network.layers['X'],
                                                  target=network.layers['Ae'],
                                                  w=0.3 * torch.rand(784, n_neurons),
                                                  update_rule=post_pre,
                                                  nu_pre=1e-4,
                                                  nu_post=1e-2,
                                                  wmin=0,
                                                  wmax=1,
                                                  norm=78.4,
                                                  decay=None)

    network.connections[('Ae', 'Ai')] = Connection(source=network.layers['Ae'],
                                                   target=network.layers['Ai'],
                                                   w=excite * torch.diag(torch.ones(network.n_neurons)),
                                                   wmin=0,
                                                   wmax=excite,
                                                   decay=None)

    network.connections[('Ai', 'Ae')] = Connection(source=network.layers['Ai'],
                                                   target=network.layers['Ae'],
                                                   w=-inhib * (torch.ones(network.n_neurons,
                                                                          network.n_neurons) - \
                                                               torch.diag(torch.ones(network.n_neurons))),
                                                   wmin=-inhib,
                                                   wmax=0,
                                                   decay=None)

else:
    path = os.path.join('..', '..', 'params', 'diehl_and_cook_2015_mnist')
    network = load_network(os.path.join(path, model_name + '.p'))
    network.connections[('X', 'Ae')].update_rule = None

# Voltage recording for excitatory and inhibitory layers.
exc_voltage_monitor = Monitor(network.layers['Ae'], ['v'], time=int(time / dt))
inh_voltage_monitor = Monitor(network.layers['Ai'], ['v'], time=int(time / dt))
network.add_monitor(exc_voltage_monitor, name='exc_voltage')
network.add_monitor(inh_voltage_monitor, name='inh_voltage')

# Load MNIST data.
dataset = MNIST(path=os.path.join('..', '..', 'data', 'MNIST'),
                       download=True)

if train:
    images, labels = dataset.get_train()
else:
    images, labels = dataset.get_test()

images = images.view(-1, 784)
images *= intensity * dt

# Record spikes during the simulation.
spike_record = torch.zeros(update_interval, int(time / dt), n_neurons)

# Neuron assignments and spike proportions.
if train:
    assignments = -torch.ones_like(torch.Tensor(n_neurons))
    proportions = torch.zeros_like(torch.Tensor(n_neurons, 10))
    rates = torch.zeros_like(torch.Tensor(n_neurons, 10))
else:
    path = os.path.join('..', '..', 'params', 'diehl_and_cook_2015_mnist')
    assignments, proportions, rates = p.load(open(os.path.join(path, '_'.join(['auxiliary', model_name]) + '.p'), 'rb'))

# Sequence of accuracy estimates.
accuracy = {'all' : [], 'proportion' : []}

if train:
    best_accuracy = 0

spikes = {}
for layer in set(network.layers) - {'X'}:
    spikes[layer] = Monitor(network.layers[layer], state_vars=['s'], time=int(time / dt))
    network.add_monitor(spikes[layer], name='%s_spikes' % layer)

# Train the network.
if train:
    print('\nBegin training.\n')
else:
    print('\nBegin test.\n')

start = t()
for i in range(n_examples):    
    if i % progress_interval == 0:
        print('Progress: %d / %d (%.4f seconds)' % (i, n_examples, t() - start))
        start = t()
    
    if i % update_interval == 0 and i > 0:
        # Get network predictions.
        all_activity_pred = all_activity(spike_record, assignments, 10)
        proportion_pred = proportion_weighting(spike_record, assignments, proportions, 10)

        # Compute network accuracy according to available classification strategies.
        accuracy['all'].append(100 * torch.sum(labels[i - update_interval:i].long() \
                                                == all_activity_pred) / update_interval)
        accuracy['proportion'].append(100 * torch.sum(labels[i - update_interval:i].long() \
                                                        == proportion_pred) / update_interval)

        print('\nAll activity accuracy: %.2f (last), %.2f (average), %.2f (best)' \
                        % (accuracy['all'][-1], np.mean(accuracy['all']), np.max(accuracy['all'])))
        print('Proportion weighting accuracy: %.2f (last), %.2f (average), %.2f (best)\n' \
                        % (accuracy['proportion'][-1], np.mean(accuracy['proportion']),
                          np.max(accuracy['proportion'])))

        if train:
            if any([x[-1] > best_accuracy for x in accuracy.values()]):
                print('New best accuracy! Saving network parameters to disk.\n')
                
                # Save network to disk.
                if train:
                    path = os.path.join('..', '..', 'params', 'diehl_and_cook_2015_mnist')
                    if not os.path.isdir(path):
                        os.makedirs(path)

                    network.save(os.path.join(path, model_name + '.p'))
                    p.dump((assignments, proportions, rates), open(os.path.join(path, '_'.join(['auxiliary', model_name]) + '.p'), 'wb'))

                best_accuracy = max([x[-1] for x in accuracy.values()])

            # Assign labels to excitatory layer neurons.
            assignments, proportions, rates = assign_labels(spike_record, labels[i - update_interval:i], 10, rates)
    
    # Get next input sample.
    image = images[i]
    sample = poisson(datum=image, time=int(time / dt))
    inpts = {'X' : sample}
    
    # Run the network on the input.
    print(int(time / dt))
    print(sample.size())
    network.run(inpts=inpts, time=time)

    while spikes['Ae'].get('s').t().sum() < 5:
        image *= 2
        sample = poisson(datum=image, time=int(time / dt))
        inpts = {'X' : sample}
        network.run(inpts=inpts, time=int(time / dt))
    
    # Get voltage recording.
    exc_voltages = exc_voltage_monitor.get('v')
    inh_voltages = inh_voltage_monitor.get('v')
    
    # Add to spikes recording.
    spike_record[i % update_interval] = spikes['Ae'].get('s').t()

    # Optionally plot various simulation information.
    if plot:
        inpt = inpts['X'].view(int(time / dt), 784).sum(0).view(28, 28)
        input_exc_weights = network.connections[('X', 'Ae')].w
        square_weights = get_square_weights(input_exc_weights.view(784, n_neurons), n_sqrt, 28)
        square_assignments = get_square_assignments(assignments, n_sqrt)
        voltages = {'Ae' : exc_voltages, 'Ai' : inh_voltages}
        
        if i == 0:
            inpt_axes, inpt_ims = plot_input(images[i].view(28, 28), inpt, label=labels[i])
            spike_ims, spike_axes = plot_spikes({layer : spikes[layer].get('s') for layer in spikes})
            weights_im = plot_weights(square_weights)
            assigns_im = plot_assignments(square_assignments)
            perf_ax = plot_performance(accuracy)
            voltage_ims, voltage_axes = plot_voltages(voltages)
            
        else:
            inpt_axes, inpt_ims = plot_input(images[i].view(28, 28), inpt, label=labels[i], axes=inpt_axes, ims=inpt_ims)
            spike_ims, spike_axes = plot_spikes({layer : spikes[layer].get('s') for layer in spikes},
                                                ims=spike_ims, axes=spike_axes)
            weights_im = plot_weights(square_weights, im=weights_im)
            assigns_im = plot_assignments(square_assignments, im=assigns_im)
            perf_ax = plot_performance(accuracy, ax=perf_ax)
            voltage_ims, voltage_axes = plot_voltages(voltages, ims=voltage_ims, axes=voltage_axes)
        
        plt.pause(1e-8)
    
    network._reset()  # Reset state variables.

print('Progress: %d / %d (%.4f seconds)' % (n_examples, n_examples, t() - start))

i += 1

# Get network predictions.
all_activity_pred = all_activity(spike_record, assignments, 10)
proportion_pred = proportion_weighting(spike_record, assignments, proportions, 10)

# Compute network accuracy according to available classification strategies.
accuracy['all'].append(100 * torch.sum(labels[i - update_interval:i].long() \
                                        == all_activity_pred) / update_interval)
accuracy['proportion'].append(100 * torch.sum(labels[i - update_interval:i].long() \
                                                == proportion_pred) / update_interval)

print('\nAll activity accuracy: %.2f (last), %.2f (average), %.2f (best)' \
                % (accuracy['all'][-1], np.mean(accuracy['all']), np.max(accuracy['all'])))
print('Proportion weighting accuracy: %.2f (last), %.2f (average), %.2f (best)' \
                % (accuracy['proportion'][-1], np.mean(accuracy['proportion']),
                  np.max(accuracy['proportion'])))

if train:
    if any([x[-1] > best_accuracy for x in accuracy.values()]):
        print('New best accuracy! Saving network parameters to disk.\n')
        
        # Save network to disk.
        if train:
            path = os.path.join('..', '..', 'params', 'diehl_and_cook_2015_mnist')
            if not os.path.isdir(path):
                os.makedirs(path)

            network.save(os.path.join(path, model_name + '.p'))
            p.dump((assignments, proportions, rates), open(os.path.join(path, '_'.join(['auxiliary', model_name]) + '.p'), 'wb'))

        best_accuracy = max([x[-1] for x in accuracy.values()])

if train:
    print('\nTraining complete.\n')
else:
    print('\nTest complete.\n')

print('Average accuracies:\n')
for scheme in accuracy.keys():
    print('\t%s: %.2f' % (scheme, np.mean(accuracy[scheme])))

# Save results to disk.
path = os.path.join('..', '..', 'results', 'diehl_and_cook_2015_mnist')
if not os.path.isdir(path):
    os.makedirs(path)

if train:
    to_write = params + [np.max(accuracy['all']), np.max(accuracy['proportion'])]
else:
    to_write = test_params + [np.mean(accuracy['all']), np.mean(accuracy['proportion'])]

to_write = [str(x) for x in to_write]

if train:
    name = 'train.csv'
else:
    name = 'test.csv'

if not os.path.isfile(os.path.join(path, name)):
    with open(os.path.join(path, name), 'w') as f:
        f.write('random seed,no. neurons,no. train,no. test,excitation,' + \
                'inhibition,sim. time,timestep,intensity,progress int.,' + \
                'update int.,all activity,proportion weighting\n')

with open(os.path.join(path, name), 'a') as f:
    f.write(','.join(to_write) + '\n')
