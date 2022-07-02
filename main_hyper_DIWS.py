# Hyperparameter tuning for DIWS using Tree Parzen Estimator (TPE).
#
# https://github.com/ejoone/DIWS-ABSC
#
# Adapted from Trusca, Wassenberg, Frasincar and Dekker (2020).
# https://github.com/mtrusca/HAABSA_PLUS_PLUS
#
# Truşcǎ M.M., Wassenberg D., Frasincar F., Dekker R. (2020) A Hybrid Approach for Aspect-Based Sentiment Analysis Using
# Deep Contextual Word Embeddings and Hierarchical Attention. In: Bielikova M., Mikkonen T., Pautasso C. (eds) Web
# Engineering. ICWE 2020. Lecture Notes in Computer Science, vol 12128. Springer, Cham.
# https://doi.org/10.1007/978-3-030-50578-3_25

import json
import os
import pickle
from functools import partial
from bson import json_util
from hyperopt import hp, tpe, fmin, Trials, STATUS_OK
import DIWS_hyper
from config import *
from load_data import *

global eval_num, best_loss, best_hyperparams


def main():
    """
    Runs hyperparameter tuning for each domain specified in domains.

    :return:
    """
    runs = 10
    n_iter = 15

    # Name, year, train size.
    apex_domain = ["Apex", 2004, None]
    camera_domain = ["Camera", 2004, None]
    hotel_domain = ["hotel", 2015, None]
    nokia_domain = ["Nokia", 2004, None]

    domains = [apex_domain, camera_domain, hotel_domain, nokia_domain]

    for domain in domains:
        run_hyper(domain=domain[0], year=domain[1], size=domain[2], runs=runs, n_iter=n_iter)


def run_hyper(domain, year, size, runs, n_iter):
    """
    Runs hyperparameter tuning for the specified domain.

    :param domain: the domain
    :param year: the year of the dataset
    :param size: the size of the training set (None if the dataset is not split)
    :param runs: the number of hyperparameter tuning runs
    :param n_iter: the number of iterations for each hyperparameter tuning run
    :return:
    """

    FLAGS.source_domain = "Creative"
    FLAGS.source_year = 2004
    FLAGS.target_domain = domain
    FLAGS.target_year = year
    FLAGS.n_iter = n_iter

    path = "hyper_results/DIWS_model/" + domain + "/" + str(n_iter) + "/"

    FLAGS.train_path = "data/programGeneratedData/BERT/" + FLAGS.source_domain + "/768_" + FLAGS.source_domain + "_train_" + str(
        FLAGS.source_year) + "_BERT.txt"
    FLAGS.train_path_target = "data/programGeneratedData/BERT/" + FLAGS.target_domain + "/768_" + FLAGS.target_domain + "_train_" + str(
        FLAGS.target_year) + "_BERT.txt"

    FLAGS.train_embedding = "data/programGeneratedData/" + FLAGS.embedding_type + "_" + FLAGS.source_domain + "_" + str(
        FLAGS.source_year) + "_" + str(FLAGS.embedding_dim) + ".txt"
    FLAGS.test_embedding = "data/programGeneratedData/" + FLAGS.embedding_type + "_" + FLAGS.target_domain + "_" + str(
        FLAGS.target_year) + "_" + str(FLAGS.embedding_dim) + ".txt"
    FLAGS.source_embedding = "data/programGeneratedData/" + FLAGS.embedding_type + "_" + FLAGS.source_domain + "_" + str(
        FLAGS.source_year) + "_" + str(FLAGS.embedding_dim) + ".txt"
    FLAGS.target_embedding = "data/programGeneratedData/" + FLAGS.embedding_type + "_" + FLAGS.target_domain + "_" + str(
        FLAGS.target_year) + "_" + str(FLAGS.embedding_dim) + ".txt"

    train_size_source, test_size_source, train_polarity_vector, test_polarity_vector = load_hyper_data(FLAGS, True)
    train_size_target, test_size_target, train_polarity_vector_target, test_polarity_vector_target = load_hyper_data_target(
        FLAGS, True)
    train_size = train_size_source + train_size_target
    test_size = test_size_source + test_size_target

    # Define variable spaces for hyperparameter optimization to run over.
    global eval_num, best_loss, best_hyperparams
    eval_num = 0
    best_loss = None
    best_hyperparams = None

    lcr_space = [
        # hp.choice('learning_rate', [0.001, 0.005, 0.02, 0.05, 0.06, 0.07, 0.08, 0.09, 0.01, 0.1]),
        hp.choice('learning_rate', [0.0005, 0.001, 0.005]),
        hp.choice('momentum', [0.85, 0.9, 0.95, 0.99]),
        hp.choice('epochs_hyper', [5, 10, 15, 20]),
        hp.choice('batch_size_hyper', [5, 10, 15, 20, 25, 30]),
    ]

    for i in range(runs):
        print("Optimizing New Model\n")
        run_a_trial(test_size, lcr_space, path, )
        plot_best_model(path)


def diws_objective(hyperparams, test_size, path):
    """
    Method adapted from Trusca et al. (2020), no original docstring provided.

    :param hyperparams: hyperparameters (learning rate, keep probability, momentum and L2 regularization)
    :param test_size: size of the test set
    :param path: save path
    :return:
    """
    global eval_num, best_loss, best_hyperparams

    eval_num += 1
    (learning_rate, momentum, epochs_hyper, batch_size_hyper) = hyperparams
    print("Current hyperparameters: " + str(hyperparams))

    l = DIWS_hyper.main(FLAGS.hyper_train_path, FLAGS.hyper_train_path_target, FLAGS.hyper_eval_path,
                        FLAGS.hyper_eval_path_target, learning_rate, momentum, epochs_hyper, batch_size_hyper)

    if best_loss is None or -l < best_loss:
        best_loss = -l
        best_hyperparams = hyperparams

    result = {
        'loss': -l,
        'status': STATUS_OK,
        'space': hyperparams,
    }

    save_json_result(str(l), result, path)

    return result


# Run a hyperparameter optimization trial.
def run_a_trial(test_size, lcr_space, path):
    """
    Method adapted from Trusca et al. (2020), no original docstring provided.

    :param test_size: size of the test set
    :param lcr_space: tuning space for LCR-Rot-hop++ method
    :param path: save path
    :return:
    """
    max_evals = nb_evals = 1

    print("Attempt to resume a past training if it exists:")

    try:
        # https://github.com/hyperopt/hyperopt/issues/267
        trials = pickle.load(open(path + "results.pkl", "rb"))
        print("Found saved Trials! Loading...")
        max_evals = len(trials.trials) + nb_evals
        print("Rerunning from {} trials to add another one.".format(len(trials.trials)))
    except:
        trials = Trials()
        print("Starting from scratch: new trials.")

    objective = diws_objective
    partial_objective = partial(objective, test_size=test_size, path=path)
    space = lcr_space

    best = fmin(
        # lcr_altv4_objective/lcr_fine_tune_objective.
        fn=partial_objective,
        # lcrspace/finetunespace.
        space=space,
        algo=tpe.suggest,
        trials=trials,
        max_evals=max_evals
    )
    pickle.dump(trials, open(path + "results.pkl", "wb"))

    print("OPTIMIZATION STEP COMPLETE.\n")


def print_json(result):
    """
    Method obtained from Trusca et al. (2020), no original docstring provided.

    :param result:
    :return:
    """
    """Pretty-print a jsonable structure (e.g.: result)."""
    print(json.dumps(
        result,
        default=json_util.default, sort_keys=True,
        indent=4, separators=(',', ': ')
    ))


def save_json_result(model_name, result, path):
    """
    Save json to a directory and a filename. Method obtained from Trusca et al. (2020).

    :param model_name:
    :param result:
    :param path:
    :return:
    """
    result_name = '{}.txt.json'.format(model_name)
    if not os.path.exists(path):
        os.makedirs(path)
    with open(os.path.join(path, result_name), 'w') as f:
        json.dump(
            result, f,
            default=json_util.default, sort_keys=True,
            indent=4, separators=(',', ': ')
        )


def load_json_result(best_result_name, path):
    """
    Load json from a path (directory + filename). Method obtained from Trusca et al. (2020).

    :param best_result_name:
    :param path:
    :return:
    """
    result_path = os.path.join(path, best_result_name)
    with open(result_path, 'r') as f:
        return json.JSONDecoder().decode(
            f.read()
        )


def load_best_hyperspace(path):
    """
    Method obtained from Trusca et al. (2020), no original docstring provided.

    :param path:
    :return:
    """
    results = [
        f for f in list(sorted(os.listdir(path))) if 'json' in f
    ]
    if len(results) == 0:
        return None

    best_result_name = results[-1]
    return load_json_result(best_result_name, path)["space"]


def plot_best_model(path):
    """
    Plot the best model found yet. Method obtained from Trusca et al. (2020).

    :param path:
    :return:
    """
    space_best_model = load_best_hyperspace(path)
    if space_best_model is None:
        print("No best model to plot. Continuing...")
        return

    print("Best hyperspace yet:")
    print_json(space_best_model)


if __name__ == "__main__":
    main()
