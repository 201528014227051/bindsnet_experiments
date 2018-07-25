#!/bin/bash
#
#SBATCH --partition=longq
#SBATCH --time=02-00:00:00
#SBATCH --mem=8000
#SBATCH --account=rkozma
#SBATCH --output=../../output/diehl_and_cook_2015_mnist_%j.out
#SBATCH --cpus-per-task=8

seed=${1:-0}
n_neurons=${2:-100}
n_train=${3:-60000}
n_test=${4:-10000}
inhib=${5:-25.0}
time=${6:-350}
theta_plus=${7:-0.05}
theta_decay=${8:-1e-7}
intensity=${9:-0.5}
X_Ae_decay=${10:-0.5}
gram_size=${11:-2}

cd ../../../scripts/mnist/
source activate py36

echo $seed $n_neurons $n_train $n_test $excite $inhib $time $theta_plus $theta_decay $intensity $X_Ae_decay $gram_size

python diehl_and_cook_2015.py --train --seed $seed --n_neurons $n_neurons --n_train $n_train \
							  --n_test $n_test --inhib $inhib --time $time \
							  --theta_plus $theta_plus --theta_decay $theta_decay \
							  --intensity $intensity --X_Ae_decay $X_Ae_decay --gram_size $gram_size\
                              >> train_$seed_$n_neurons_$n_train_$n_test_$inhib_$time_$theta_plus_$theta_decay_$intensity_$X_Ae_decay_$gram_size
python diehl_and_cook_2015.py --test --seed $seed --n_neurons $n_neurons --n_train $n_train \
							  --n_test $n_test --inhib $inhib --time $time \
							  --theta_plus $theta_plus --theta_decay $theta_decay \
							  --intensity $intensity --X_Ae_decay $X_Ae_decay --gram_size $gram_size\
                              >> test_$seed_$n_neurons_$n_train_$n_test_$inhib_$time_$theta_plus_$theta_decay_$intensity_$X_Ae_decay_$gram_size

exit
