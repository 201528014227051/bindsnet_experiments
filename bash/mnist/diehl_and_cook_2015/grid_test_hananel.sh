for seed in 1
do
    for n_neurons in 200 300 400 500 600 700 800
    do
        for n_train in 60000
        do
            for n_test in 10000
            do
                for inhib in 400 500
                do
                    for time in 200 250 300 350
                    do
                        for theta_plus in 0.05
                        do
                            for theta_decay in 1e-7
                            do
                                for intensity in 0.45
                                do
                                    for X_Ae_decay in 0.0 0.5
                                    do
                                            sbatch test.sh $seed $n_neurons $n_train $n_test \
                                                $inhib $time $theta_plus $theta_decay \
                                                $intensity $X_Ae_decay
                                    done
                                done
                            done
                        done
                    done
                done
            done
        done
    done
done
