import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt

from experiments import ROOT_DIR

benchmark_path = os.path.join(ROOT_DIR, 'benchmark')
figure_path = os.path.join(ROOT_DIR, 'figures')

if not os.path.isdir(benchmark_path):
    os.makedirs(benchmark_path)


def main(start=100, stop=1000, step=100, time=1000, interval=100):
    name = f'benchmark_{start}_{stop}_{step}_{time}'
    f = os.path.join(benchmark_path, name + '.csv')
    df = pd.read_csv(f, index_col=0)

    for c in df.columns:
        plt.plot(df[c], label=c)

    plt.title('Benchmark comparison of SNN simulation frameworks')
    plt.xticks(range(0, stop + interval, interval))
    plt.xlabel('No. of input and output neurons')
    plt.ylabel('Simulation time (seconds)')
    plt.legend()

    plt.savefig(os.path.join(figure_path, name + '.png'))

    plt.show()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', type=int, default=100)
    parser.add_argument('--stop', type=int, default=1000)
    parser.add_argument('--step', type=int, default=100)
    parser.add_argument('--time', type=int, default=1000)
    parser.add_argument('--interval', type=int, default=1000)
    args = parser.parse_args()

    main(start=args.start, stop=args.stop, step=args.step, time=args.time, interval=args.interval)