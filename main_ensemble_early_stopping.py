#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jan 31 18:53:31 2018

@author: stenly
"""
import numpy as np
import tensorflow as tf
import random as rn

# The below is necessary in Python 3.2.3 onwards to
# have reproducible behavior for certain hash-based operations.
# See these references for further details:
# https://docs.python.org/3.4/using/cmdline.html#envvar-PYTHONHASHSEED
# https://github.com/keras-team/keras/issues/2280#issuecomment-306959926

#import os
#os.environ['PYTHONHASHSEED'] = '0'
#
## The below is necessary for starting Numpy generated random numbers
## in a well-defined initial state.
#
#np.random.seed(42)
#
## The below is necessary for starting core Python generated random numbers
## in a well-defined state.
#
#rn.seed(12345)
#
## Force TensorFlow to use single thread.
## Multiple threads are a potential source of
## non-reproducible results.
## For further details, see: https://stackoverflow.com/questions/42022950/which-seeds-have-to-be-set-where-to-realize-100-reproducibility-of-training-res
#
#session_conf = tf.ConfigProto(intra_op_parallelism_threads=1, inter_op_parallelism_threads=1)
#
#from keras import backend as K
#
## The below tf.set_random_seed() will make random number generation
## in the TensorFlow backend have a well-defined initial state.
## For further details, see: https://www.tensorflow.org/api_docs/python/tf/set_random_seed
#
#tf.set_random_seed(1234)
#
#sess = tf.Session(graph=tf.get_default_graph(), config=session_conf)
#K.set_session(sess)
#
## Rest of code follows ...

import os.path
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import stl10
#import cifar100
import cifar10
import cifar100_subset
import cifar100_subset_validation
import cifar100_custom_subset
import cifar100_model
import imagenet_cats
import squeezenet_model
import stl10_model
import train_keras_model
import transfer_learning
from keras.models import load_model
import gc
import pickle
import image_utils
import draw_results
import argparse
import time
import itertools
from ModifiedSGD import ModifiedSGD
import scipy
from sklearn import svm
from debugging_tools import varname


def delete_model(model=None, history=None):
    K.clear_session()
    if model is not None:
        del model
    if history is not None:
        del history
    for i in range(20):
        gc.collect()


def train(num_models, num_epochs):
    for i in range(num_models):
        print('training model number: ' + str(i+1) + ' out of: ' + str(num_models))
        lr_rate = 1e-3
        model = model_lib.build_classifier_model(dataset)
        lr_scheduler = model_lib.lr_scheduler_generator(lr_rate)
        model_output_path = os.path.join(model_dir, 'stl10_early_stop_' + str(num_epochs) + '_' + str(i))
        history = train_keras_model.train_model(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                dataset.y_test_labels, model_output_path=model_output_path,
                                                epochs=num_epochs, lr_scheduler=lr_scheduler)
        train_keras_model.evaluate_model(model, dataset.x_train, dataset.y_train_labels, dataset.x_test, dataset.y_test_labels)
        delete_model(model, history)


def early_stop_name_with_stops(num_epochs, epoch_stop, num_model):
    name = 'stl10_early_stop_epoch_' + str(epoch_stop) + "_out_of_" + str(num_epochs) + '_' + str(num_model)
    history_name = name + '_history'
    return name, history_name

def early_stop_name_with_stops_curriculum(num_epochs, epoch_stop, num_model):
    name = 'stl10_early_stop_epoch_' + str(epoch_stop) + "_out_of_" + str(num_epochs) + '_' + str(num_model) + '_curriculum_'
    history_name = name + '_history'
    return name, history_name


def evaluate(num_models, num_epochs, paths=None):
    res = np.zeros((dataset.test_size, dataset.n_classes))
    for i in range(num_models):
        print('getting results for model number: ' + str(i+1) + ' out of: ' + str(num_models))
        if paths is None:
            model_path = os.path.join(model_dir, 'stl10_early_stop_' + str(num_epochs) + '_' + str(i))
        else:
            model_path = paths[i]
        model = load_model(model_path)
        predicted_x = model.predict(dataset.x_test)
        res += predicted_x
        del model
        gc.collect()
    predicted = np.argmax(res, axis=1)
    accuracy = np.mean(predicted == dataset.y_test)
    print('The accuracy is: ' + str(accuracy))
    return accuracy


def train_with_stops(num_models, num_epochs, stop_iter, num_func=early_stop_name_with_stops ,data_scheduler=None):
    for i in range(num_models):
        lr_rate = 1e-3
        print('training model number: ' + str(i+1) + ' out of: ' + str(num_models))
        lr_scheduler = model_lib.lr_scheduler_generator(lr_rate)
        model = model_lib.build_classifier_model(dataset)
        for epoch_stop in range(stop_iter, num_epochs+stop_iter, stop_iter):
            cur_lr_rate = lr_scheduler(epoch_stop+1)
            def new_scheduler(epoch):
                return cur_lr_rate
            name, history_name = num_func(num_epochs, epoch_stop, i)
            model_output_path = os.path.join(model_dir, name)
            model_history_path = os.path.join(model_dir, history_name)
            history = train_keras_model.train_model(model, dataset.x_train, y_train_labels, x_test,
                                                    dataset.y_test_labels, model_output_path=model_output_path,
                                                    epochs=stop_iter, initial_lr=cur_lr_rate, lr_scheduler=new_scheduler)
            with open(model_history_path, 'wb') as file_pi:
                pickle.dump(history.history, file_pi)
            delete_model(history=history)
        delete_model(model=model)


def evaluate_early_stopping(num_models, num_epochs, stop_iter):
    scores = []
    for epoch_stop in range(stop_iter+60, num_epochs+stop_iter, stop_iter):
        print('epoch number: ' + str(epoch_stop))
        paths = []
        for model_num in range(num_models):
            name, _ = early_stop_name_with_stops(num_epochs, epoch_stop, model_num)
            model_output_path = os.path.join(model_dir, name)
            # model_history_path = os.path.join(model_dir, history_name)
            paths.append(model_output_path)
        score = evaluate(num_models, num_epochs, paths)
        scores.append(score)
    print(scores)
    return scores


def creatue_svm_data_scheduler():
    train_scores, test_scores = transfer_learning.get_svm_scores(transfer_values_train, dataset.y_train, transfer_values_test, y_test)
    order = transfer_learning.rank_data_according_to_score(train_scores, dataset.y_train)
    def data_scheduler(x, y, epoch):
        if epoch < 2:
            data_limit = np.int(np.ceil(len(x) * 0.1))  # 500
        elif epoch < 4:
            data_limit = np.int(np.ceil(len(x) * 0.2))  # 1000
        elif epoch < 6:
            data_limit = np.int(np.ceil(len(x) * 0.3))  # 1500
        elif epoch < 8:
            data_limit = np.int(np.ceil(len(x) * 0.4))  # 2000
        elif epoch < 10:
            data_limit = np.int(np.ceil(len(x) * 0.5))  # 2500
        elif epoch < 12:
            data_limit = np.int(np.ceil(len(x) * 0.6))  # 3000
        elif epoch < 14:
            data_limit = np.int(np.ceil(len(x) * 0.7))  # 3500
        elif epoch < 16:
            data_limit = np.int(np.ceil(len(x) * 0.8))  # 4000
        elif epoch < 18:
            data_limit = np.int(np.ceil(len(x) * 0.9))  # 4500
        elif epoch < 20:
            data_limit = np.int(np.ceil(len(x) * 0.95))  # 4750

        else:
            data_limit = np.int(np.ceil(len(x) * 1))  # 5000
        cur_examples = order[:data_limit]
        cur_examples = np.concatenate((np.random.choice(cur_examples, len(dataset.y_train) - len(cur_examples)), cur_examples))
        return x[cur_examples, :, :, :], y[cur_examples, :]
    return data_scheduler


def train_with_stops_2(num_models, num_epochs, stop_iter, num_func=early_stop_name_with_stops ,data_scheduler=None):
    for i in range(num_models):
        lr_rate = 1e-3
        print('training model number: ' + str(i+1) + ' out of: ' + str(num_models))
        lr_scheduler = model_lib.lr_scheduler_generator(lr_rate)
        model = model_lib.build_classifier_model(dataset)
        x = dataset.x_train
        y = dataset.y_train_labels
        for epoch_num in range(1, num_epochs+1):
            if epoch_num == 1:
                compile = True
            else:
                compile = False
            cur_lr_rate = lr_scheduler(epoch_num)
            def new_scheduler(epoch):
                return cur_lr_rate
            if data_scheduler is not None:
                print(dataset.y_train_labels.shape)
                x, y = data_scheduler(dataset.x_train, dataset.y_train_labels, epoch_num)
                print(y.shape)
            if epoch_num % stop_iter == 0:
                name, history_name = num_func(num_epochs, stop_iter, i)
                model_output_path = os.path.join(model_dir, name)
                model_history_path = os.path.join(model_dir, history_name)
                history = train_keras_model.train_model(model, x, y, dataset.x_test,
                                                        dataset.y_test_labels, model_output_path=model_output_path,
                                                        epochs=1, initial_lr=cur_lr_rate, lr_scheduler=new_scheduler, compile=compile)
                with open(model_history_path, 'wb') as file_pi:
                    pickle.dump(history.history, file_pi)
                delete_model(history=history)
            else:
                history = train_keras_model.train_model(model, x, y, dataset.x_test,
                                                        dataset.y_test_labels, epochs=1, initial_lr=cur_lr_rate,
                                                        lr_scheduler=new_scheduler, compile=compile)
                delete_model(history=history)

        delete_model(model=model)


def train_network_using_batch():
    batch_size = 4
    model = model_lib.build_classifier_model(dataset)
    train_keras_model.compile_model(model)
    history = train_keras_model.train_model_batch(model, dataset.x_train, dataset.y_train_labels, dataset.x_test, dataset.y_test_labels,
                                                  num_training_phases=1, epoch_per_phase=[5], batch_size=batch_size)
    print(history['loss'])
    print(history['acc'])


def check_on_real_data(output_path, batch_size=128,
                       optimizer='adam', initial_lr=1e-3, verbose=False,
                       test_each_epoch=True):
    model = model_lib.build_classifier_model(dataset)
    train_keras_model.compile_model(model)
    history = train_keras_model.train_model_batch(model, dataset.x_train, dataset.y_train_labels, dataset.x_test, dataset.y_test_labels,
                                                  num_training_phases=8, epoch_per_phase=model_lib.phases_epochs(),
                                                  batch_size=batch_size, lr_scheduler=model_lib.lr_scheduler_phases,
                                                  test_each_epoch=True, model_output_path=output_path,
                                                  optimizer=optimizer, initial_lr=initial_lr,
                                                  verbose=verbose)
    predicted_x = model.predict(dataset.x_test)
    predicted = np.argmax(predicted_x, axis=1)
    accuracy = np.mean(predicted == dataset.y_test)
    print('The accuracy is: ' + str(accuracy))


def curriculum_model(name, anti_corriculum=False, random=False, batch_size=128,
                     optimizer='adam', initial_lr=1e-3, verbose=True,
                     test_each_epoch=True):
    epochs, curriculum_data_function = model_lib.corriculum_svm_based_training_data(dataset,
                                                                                    anti_corriculum=anti_corriculum,
                                                                                    random=random)
    model = model_lib.build_classifier_model(dataset)
    train_keras_model.compile_model(model)
    save_scheduler = train_keras_model.early_stopping_save_scheduler(model_dir, name, 3)
    history = train_keras_model.train_model_batch(model, dataset.x_train, dataset.y_train_labels, dataset.x_test, dataset.y_test_labels,
                                                  batch_size=batch_size, lr_scheduler=model_lib.lr_scheduler_phases,
                                                  num_training_phases=len(epochs), epoch_per_phase=epochs,
                                                  data_function=curriculum_data_function, verbose=verbose,
                                                  test_each_epoch=test_each_epoch,
                                                  model_save_scheduler=save_scheduler, initial_lr=initial_lr,
                                                  optimizer=optimizer)

    return history


def decrease_lr_scheduler_generator(dataset, batch_size=100):
    size_data = dataset.x_train.shape[0]
    batchs_per_epoch = size_data // batch_size

    def decrease_lr_scheduler(initial_lr, batch, history):

        # return initial_lr
        if batch < 20 * batchs_per_epoch:
            return initial_lr
        elif batch < 40 * batchs_per_epoch:
            return initial_lr / 2
        elif batch < 50 * batchs_per_epoch:
            return initial_lr / 4
        elif batch < 60 * batchs_per_epoch:
            return initial_lr / 8
        elif batch < 70 * batchs_per_epoch:
            return initial_lr / 16
        elif batch < 80 * batchs_per_epoch:
            return initial_lr / 32
        elif batch < 90 * batchs_per_epoch:
            return initial_lr / 64
        else:
            return initial_lr / 128
    return decrease_lr_scheduler


def cycle_lr_scheduler_generator(min_lr, max_lr, step_size_batchs,
                                 decay=1, batch_to_drop=1000):
    cycle_size = step_size_batchs * 2
    def cycle_lr_scheduler(initial_lr, batch, history):
        cur_max_lr = max(max_lr / (decay ** (batch//batch_to_drop)), min_lr)
        place_in_cycle = batch % cycle_size
        if place_in_cycle >= step_size_batchs:
            place_in_cycle = cycle_size - place_in_cycle
        lr = (cur_max_lr - min_lr) * (place_in_cycle / step_size_batchs) + min_lr
        return lr

    return cycle_lr_scheduler

def cycle_set_param_lr_scheduler_generator(min_lr, max_lr, step_size_batchs):
    gamma = (max_lr / min_lr) ** (1/step_size_batchs)
    cycle_size = step_size_batchs * 2
    step_lr_vals = [min_lr * gamma**(batch) for batch in range(step_size_batchs)]
    lr_vals = np.concatenate((step_lr_vals, step_lr_vals[::-1]))

    def cycle_lr_scheduler(initial_lr, batch, history):
        return lr_vals[batch % cycle_size]

    return cycle_lr_scheduler

def expo_lr_scheduler_generator(batches_to_increase, amount, starting_percent, to_increase=False):
    lr_multipliers = [1]
    cur_percent = starting_percent
    cur_batch = 0
    while cur_percent < 1:
        cur_percent *= amount
        cur_batch += batches_to_increase
        if to_increase:
            lr_multipliers.append(min(lr_multipliers[-1]*amount, 1/starting_percent))

        else:
            lr_multipliers.append(max(lr_multipliers[-1]/amount, starting_percent))

    def decrease_lr_scheduler(initial_lr, batch, history):

        increase_idx = batch // batches_to_increase
        if increase_idx >= len(lr_multipliers):
            return initial_lr * lr_multipliers[-1]
        else:
            return initial_lr * lr_multipliers[increase_idx]

    return decrease_lr_scheduler


def expo_loss_tresh_lr_scheduler_generator(batches_to_increase, amount, starting_percent, to_increase=False, treshold=7.8):
    lr_multipliers = [1]
    cur_percent = starting_percent
    cur_batch = 0
    while cur_percent < 1:
        cur_percent *= amount
        cur_batch += batches_to_increase
        if to_increase:
            lr_multipliers.append(min(lr_multipliers[-1]*amount, 1/starting_percent))

        else:
            lr_multipliers.append(max(lr_multipliers[-1]/amount, starting_percent))

    time_passed_treshold = 0
    def decrease_lr_scheduler(initial_lr, batch, history):
        nonlocal time_passed_treshold
        if batch == 0:
            time_passed_treshold = 0

#        if len(history["loss"]) >= 20 and (time_passed_treshold * 500 <= batch):
        if time_passed_treshold * treshold <= batch:
            if all(np.array(history["loss"][-20:]) < treshold):
                time_passed_treshold += 1
                
        if time_passed_treshold >= len(lr_multipliers):
            return initial_lr * lr_multipliers[-1]
        else:
            return initial_lr * lr_multipliers[time_passed_treshold]

    return decrease_lr_scheduler


def find_lr_generator():
    cur_lr = 1e-6
    increase = 1.005
    def find_lr_scheduler(initial_lr, batch, history):
        nonlocal cur_lr
        if batch == 0:
            cur_lr = 1e-6
        cur_lr *= increase
        return cur_lr
    return find_lr_scheduler


def exponent_decay_lr_generator(decay_rate, minimum_lr, batch_to_decay):
    cur_lr = None
    def exponent_decay_lr(initial_lr, batch, history):
        nonlocal cur_lr
        if batch == 0:
            cur_lr = initial_lr
        if (batch % batch_to_decay) == 0 and batch !=0:
            new_lr = cur_lr / decay_rate
            cur_lr = max(new_lr, minimum_lr)
        return cur_lr
    return exponent_decay_lr

def combine_exponent_decay_lr_generators(decay1, min_lr1, batch_decay1,
                                         decay2, min_lr2, batch_decay2,
                                         initial_lr1, initial_lr2,
                                         switch_batch):
    first_lr_func = exponent_decay_lr_generator(decay1, min_lr1, batch_decay1)
    second_lr_func = exponent_decay_lr_generator(decay2, min_lr2, batch_decay2)
    def combine_exponent_decay_lr(_, batch, history):
        ## since the lr functions depend on getting batches
        ## from 0, i call both function every iterations,
        ## even though im only using one.
        first_lr = first_lr_func(initial_lr1, batch, history)
        second_lr = second_lr_func(initial_lr2, batch, history)
        if batch <= switch_batch:
            return first_lr
        else:
            return second_lr
        
    return combine_exponent_decay_lr

#def naive_corriculum_data_function_generator(dataset, order, batch_size=100):
#
#    size_data = dataset.x_train.shape[0]
#    batchs_per_epoch = size_data // batch_size
#    
#    def data_function(x, y, batch, history):
#        if batch < 2 * batchs_per_epoch:
#            data_limit = np.int(np.ceil(size_data * 0.1))  # 10000
#        elif batch < 4 * batchs_per_epoch:
#            data_limit = np.int(np.ceil(size_data * 0.3))  # 20000
#        elif batch < 6 * batchs_per_epoch:
#            data_limit = np.int(np.ceil(size_data * 0.5))  # 30000
#        elif batch < 7 * batchs_per_epoch:
#            data_limit = np.int(np.ceil(size_data * 0.6))  # 30000
#        elif batch < 9 * batchs_per_epoch:
#            data_limit = np.int(np.ceil(size_data * 0.9))  # 30000
#        elif batch < 10 * batchs_per_epoch:
#            data_limit = np.int(np.ceil(size_data * 0.95))
#        else:
#            data_limit = np.int(np.ceil(size_data * 1))  # 50000
#        new_data = order[:data_limit]
#        return x[new_data, :, :, :], y[new_data, :]
#
#    return data_function

def naive_corriculum_data_function_generator(dataset, order, batch_size=100):

    size_data = dataset.x_train.shape[0]
    batchs_per_epoch = size_data // batch_size
    
    cur_percent = 1
    cur_data_x = dataset.x_train
    cur_data_y = dataset.y_test_labels
    
    def data_function(x, y, batch, history, model):
        nonlocal cur_percent, cur_data_x, cur_data_y
        update_data = False
        if batch < 2 * batchs_per_epoch:
            percent = 0.1
            if cur_percent != percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent)) 
                update_data = True
        elif batch < 4 * batchs_per_epoch:
            percent = 0.3
            if cur_percent != percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent)) 
                update_data = True
        elif batch < 6 * batchs_per_epoch:
            percent = 0.5
            if cur_percent != percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent)) 
                update_data = True
        elif batch < 7 * batchs_per_epoch:
            percent = 0.6
            if cur_percent != percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent)) 
                update_data = True
        elif batch < 9 * batchs_per_epoch:
            percent = 0.9
            if cur_percent != percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent)) 
                update_data = True
        elif batch < 10 * batchs_per_epoch:
            percent = 0.95
            if cur_percent != percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent)) 
                update_data = True
        else:
            percent = 1
            if cur_percent != percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent)) 
                update_data = True                
        if update_data:
            new_data = order[:data_limit]
            cur_data_x = dataset.x_train[new_data, :, :, :]
            cur_data_y = dataset.y_train_labels[new_data, :]
        return cur_data_x, cur_data_y

    return data_function


def linear_data_function_generator(dataset, order, batches_to_increase, increase_amount, batch_size=100):

    size_data = dataset.x_train.shape[0]
    
    cur_percent = 0
    cur_data_x = dataset.x_train
    cur_data_y = dataset.y_test_labels
    
    
    def data_function(x, y, batch, history, model):
        nonlocal cur_percent, cur_data_x, cur_data_y
        
        if batch % batches_to_increase == 0:
            percent = min(cur_percent+increase_amount, 1)
            if percent != cur_percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent))
                new_data = order[:data_limit]
                cur_data_x = dataset.x_train[new_data, :, :, :]
                cur_data_y = dataset.y_train_labels[new_data, :]               
        return cur_data_x, cur_data_y

    return data_function

def self_pace_exponent_data_function_generator(dataset, batches_to_increase, increase_amount,
                                               starting_percent, batch_size=100,
                                               anti=False):
    size_data = dataset.x_train.shape[0]
    
    cur_percent = 1
    cur_data_x = dataset.x_train
    cur_data_y = dataset.y_test_labels
    
    def data_function(x, y, batch, history, model):
        nonlocal cur_percent, cur_data_x, cur_data_y
        
        if batch % batches_to_increase == 0:
            if batch == 0:
                percent = starting_percent
            else:
                percent = min(cur_percent*increase_amount, 1)
            if percent != cur_percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent))
                loss_order = balance_order(order_by_loss(dataset, model), dataset)
                if anti:
                    loss_order = loss_order[::-1]
                new_data = loss_order[:data_limit]
                cur_data_x = dataset.x_train[new_data, :, :, :]
                cur_data_y = dataset.y_train_labels[new_data, :]               
        return cur_data_x, cur_data_y

    return data_function

def exponent_data_function_generator(dataset, order, batches_to_increase, increase_amount, starting_percent, batch_size=100):

    size_data = dataset.x_train.shape[0]
    
    cur_percent = 1
    cur_data_x = dataset.x_train
    cur_data_y = dataset.y_test_labels
    
    
    def data_function(x, y, batch, history, model):
        nonlocal cur_percent, cur_data_x, cur_data_y
        
        if batch % batches_to_increase == 0:
            if batch == 0:
                percent = starting_percent
            else:
                percent = min(cur_percent*increase_amount, 1)
            if percent != cur_percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent))
                new_data = order[:data_limit]
                cur_data_x = dataset.x_train[new_data, :, :, :]
                cur_data_y = dataset.y_train_labels[new_data, :]               
        return cur_data_x, cur_data_y

    return data_function

def exponent_data_change_2_first_function_generator(dataset, order,
                                                    batches_to_increase,
                                                    increase_amount, starting_percent,
                                                    batch_size=100,
                                                    first_jump=50,
                                                    second_jump=50):


    size_data = dataset.x_train.shape[0]
    
    cur_percent = 1
    cur_data_x = dataset.x_train
    cur_data_y = dataset.y_test_labels
    
    
    def data_function(x, y, batch, history, model):
        nonlocal cur_percent, cur_data_x, cur_data_y
        if batch == 0:
            percent = starting_percent
        elif batch == first_jump or batch == (first_jump + second_jump):
            percent = min(cur_percent*increase_amount, 1)
        elif (batch-(first_jump + second_jump)) > 0 and ((batch-(first_jump + second_jump)) % batches_to_increase) == 0:
            percent = min(cur_percent*increase_amount, 1)
        else:
            percent = cur_percent
    
        if percent != cur_percent:
            cur_percent = percent
            data_limit = np.int(np.ceil(size_data * percent))
            new_data = order[:data_limit]
            cur_data_x = dataset.x_train[new_data, :, :, :]
            cur_data_y = dataset.y_train_labels[new_data, :]               
        return cur_data_x, cur_data_y

    return data_function

def exponent_change_jumps_data_function_generator(dataset, order,
                                                  batches_to_increase_list, increase_amount,
                                                  starting_percent, batch_size=100):

    size_data = dataset.x_train.shape[0]
    
    cur_percent = 1
    cur_data_x = dataset.x_train
    cur_data_y = dataset.y_test_labels
    
    inc_locations = np.cumsum(batches_to_increase_list)
    def data_function(x, y, batch, history, model):
        nonlocal cur_percent, cur_data_x, cur_data_y
        if batch == 0:
            percent = starting_percent
        elif batch in inc_locations:
            percent = min(cur_percent*increase_amount, 1)
        else:
            percent = cur_percent
            
        if percent != cur_percent:
            cur_percent = percent
            data_limit = np.int(np.ceil(size_data * percent))
            new_data = order[:data_limit]
            cur_data_x = dataset.x_train[new_data, :, :, :]
            cur_data_y = dataset.y_train_labels[new_data, :]               
        return cur_data_x, cur_data_y

    return data_function


def single_step_data_function_generator(dataset, order, step_batch, starting_percent):

    size_data = dataset.x_train.shape[0]
    
    cur_percent = None
    cur_data_x = dataset.x_train
    cur_data_y = dataset.y_test_labels
    
    def data_function(x, y, batch, history, model):
        nonlocal cur_percent, cur_data_x, cur_data_y
        if batch == step_batch or  batch == 0:
            if batch == 0:
                percent = starting_percent
            else:
                percent = 1
            if percent != cur_percent:
                cur_percent = percent
                data_limit = np.int(np.ceil(size_data * percent))
                new_data = order[:data_limit]
                cur_data_x = dataset.x_train[new_data, :, :, :]
                cur_data_y = dataset.y_train_labels[new_data, :]             
        return cur_data_x, cur_data_y

    return data_function



def partial_data_function_generator(dataset, order, starting_percent, batch_size=100):

    size_data = dataset.x_train.shape[0]
    
    cur_percent = starting_percent
    data_limit = np.int(np.ceil(size_data * cur_percent))
    new_data = order[:data_limit]
    cur_data_x = dataset.x_train[new_data, :, :, :]
    cur_data_y = dataset.y_train_labels[new_data, :]   
    
    
    def data_function(x, y, batch, history, model):            
        return cur_data_x, cur_data_y

    return data_function


def exp_treshold_loss_data_function_generator(dataset, order, increase_amount,
                                              starting_percent, batch_size=100,
                                              treshold=7.8):

    size_data = dataset.x_train.shape[0]
    
    cur_percent = starting_percent
   
    data_limit = np.int(np.ceil(size_data * cur_percent))
    new_data = order[:data_limit]
     
    cur_data_x = dataset.x_train[new_data, :, :, :]
    cur_data_y =  dataset.y_train_labels[new_data, :]   
    
    
    def data_function(x, y, batch, history, model):
        nonlocal cur_percent, cur_data_x, cur_data_y
        
        if len(history["loss"]) >= 5:        
            if all(np.array(history["loss"][-5:]) < treshold):
                print(history["loss"][-5:])                
                percent = min(cur_percent*increase_amount, 1)
                if percent != cur_percent:
                    cur_percent = percent
                    data_limit = np.int(np.ceil(size_data * percent))
                    new_data = order[:data_limit]
                    cur_data_x = dataset.x_train[new_data, :, :, :]
                    cur_data_y = dataset.y_train_labels[new_data, :]
        return cur_data_x, cur_data_y

    return data_function


def adaptive_corriculum_data_function_generator(dataset, order, batch_size=100):

    size_data = dataset.x_train.shape[0]
    batchs_per_epoch = size_data // batch_size

    def data_function(x, y, batch, history, model):
        if batch < 2 * batchs_per_epoch:
            data_limit = np.int(np.ceil(size_data * 0.3))
        else:
            last_data_size = history["data_size"][-1]
            if last_data_size == size_data:
                data_limit = np.int(np.ceil(size_data * 1))
            else:
                cur_loss = history["loss"][-1]
                prev_loss = history["loss"][-2]
                # if (cur_loss/prev_loss < 0.99):
                    # data_limit = history["data_size"][-1] + (size_data // 20)
                if (batch % batchs_per_epoch == 0):
                    last_epoch_loss = np.mean(history["loss"][batch-batchs_per_epoch:])
                    prev_epoch_loss = np.mean(history["loss"][(batch - (3*batchs_per_epoch)):(batch-batchs_per_epoch)])
                    if (last_epoch_loss/prev_epoch_loss < 0.99):
                        data_limit = history["data_size"][-1] + (size_data // 20)
                    else:
                        data_limit = history["data_size"][-1]
                else:
                    data_limit = history["data_size"][-1]
        new_data = order[:data_limit]
        return x[new_data, :, :, :], y[new_data, :]

    return data_function

def adaptive_expo_corriculum_data_function_generator(dataset, order,
                                                     increase_amount, starting_percent,
                                                     batch_size=100, treshold=0.99):

    size_data = dataset.x_train.shape[0]
    
    cur_percent = starting_percent
   
    data_limit = np.int(np.ceil(size_data * cur_percent))
    new_data = order[:data_limit]
     
    cur_data_x = dataset.x_train[new_data, :, :, :]
    cur_data_y =  dataset.y_train_labels[new_data, :]   
    batchs_per_epoch = size_data // batch_size
    
    def data_function(x, y, batch, history, model):
        nonlocal cur_percent, cur_data_x, cur_data_y
        
        
        if len(history["loss"]) >= (batchs_per_epoch*2) and (batch % batchs_per_epoch == 0):
#            if np.all(history["data_size"][-1] == np.array(history["data_size"][-10:])):
            cur_loss = history["loss"][-1]
            prev_loss = history["loss"][-2]
#            last_epoch_loss = np.mean(history["loss"][batch-batchs_per_epoch:])
#            prev_epoch_loss = np.mean(history["loss"][(batch - (3*batchs_per_epoch)):(batch-batchs_per_epoch)])
#            print(last_epoch_loss)
#            print(prev_epoch_loss)
            if  cur_loss/prev_loss < treshold:
#            if (last_epoch_loss/prev_epoch_loss < 0.99):
                percent = min(cur_percent*increase_amount, 1)
                if percent != cur_percent:
                    cur_percent = percent
                    data_limit = np.int(np.ceil(size_data * percent))
                    new_data = order[:data_limit]
                    cur_data_x = dataset.x_train[new_data, :, :, :]
                    cur_data_y = dataset.y_train_labels[new_data, :]
        return cur_data_x, cur_data_y
    
    return data_function


def gad_order(reverse=False, random=False):
    with open(r"/cs/labs/daphna/guy.hacohen/project/data/cifar_100_superclass_16/gad_indexes", "rb+") as pick_file:
        order = pickle.load(pick_file)
    res = np.asarray(order)
    if reverse:
        res = np.flip(res, 0)
    if random:
        np.random.shuffle(res)
    return res


def order_according_to_model(dataset, model_lib, net_type, reverse=False, random=False):
    model = model_lib.build_classifier_model(dataset, model_type=net_type)
    train_keras_model.compile_model(model)
    predicted = model.predict(dataset.x_train)
    order = transfer_learning.rank_data_according_to_score(predicted, dataset.y_train, reverse=reverse,
                                                           random=random)
    return order

def order_according_to_trained_model(model, dataset, reverse=False, random=False):
    predicted = model.predict(dataset.x_train)
    order = transfer_learning.rank_data_according_to_score(predicted, dataset.y_train, reverse=reverse,
                                                           random=random)
    return order


def order_by_freq(dataset):
    """
    returns training order of the given dataset by freqency
    low freq images will be first, high freq images will be last
    """
    images = dataset.x_train
    num_images, h, w, c = images.shape

    ## fourier transform for getting the freq map
    images_last = images.transpose(0,3,1,2)
    freq_map = np.abs(np.fft.fft2(images_last))
    scores = np.zeros(num_images)
    for img_idx in range(num_images):
        image_score = 0
        for c_idx in range(c):
            for freq_x in range(h):
                for freq_y in range(w):
                    ## the freq at 0,0 is simply the images mean, which is usally normalized anyway.
                    ## this if makes the score invariant to it.
                    if freq_x == 0 and freq_y == 0:
                        continue
                    image_score += freq_map[img_idx, c_idx, freq_x, freq_y] / (freq_x+freq_y)
        scores[img_idx] = image_score
    ## takes the scores of every image, and produces an ordering.
    ## res[0] is the index of the "easiest" image by the scoring, res[1] is the index of a bit harder image, etc...
    res = np.asarray(sorted(range(len(scores)), key=lambda k: scores[k], reverse=True))
    return res


def order_by_prototype(dataset, reverse=False, random=False):
    num_images, h, w, c = dataset.x_train.shape
    prototypes = np.zeros((dataset.n_classes, h, w, c))
    for class_idx in range(dataset.n_classes):
        class_indexes = [i for i in range(num_images) if dataset.y_train[i] == class_idx]
        prototypes[class_idx, :, :, :] = np.mean(dataset.x_train[class_indexes, :, :, :], axis=0)

    scores = np.zeros(num_images)

    for img_idx in range(num_images):
        cur_img = dataset.x_train[img_idx, :, :, :]
        cur_proto = prototypes[dataset.y_train[img_idx], :, :, :]
        score = np.sum(np.abs(cur_img - cur_proto))
        scores[img_idx] = score

    res = np.asarray(sorted(range(len(scores)), key=lambda k: scores[k]))

    if reverse:
        res = np.flip(res, 0)
    if random:
        np.random.shuffle(res)

    return res

def order_by_small_network(dataset, model_lib=cifar100_model.Cifar100_Model()):
    file_path_cache = os.path.join(dataset.data_dir, 'small_network_order_' + dataset.name + '.pkl')

    if os.path.exists(file_path_cache):
        with open(file_path_cache, "rb") as pick_file:
            res = pickle.load(pick_file)
    else:
        epochs = 100
        size_train = dataset.x_train.shape[0]
        batch_size = 100
        num_batchs = (epochs * size_train) // batch_size
        dropout1 = 0.25
        dropout2 = 0.5
        lr = 1e-3
        reg_factor = 50e-4
        bias_reg_factor = None
        optimizer = "sgd"
        model = model_lib.build_classifier_model(dataset, model_type="small",
                                                 dropout_1_rate=dropout1, dropout_2_rate=dropout2,
                                                 reg_factor=reg_factor,
                                                 bias_reg_factor=bias_reg_factor)

        train_keras_model.compile_model(model, initial_lr=lr,
                                        loss='categorical_crossentropy',
                                        optimizer=optimizer, metrics=['accuracy'])

        history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                        dataset.y_test_labels, num_batchs, verbose=False,
                                                        batch_size=batch_size,
                                                        initial_lr=lr,
                                                        loss='categorical_crossentropy',
                                                        optimizer=optimizer, Compile=False,
                                                        model_output_path=None, metrics=['accuracy'],
                                                        reduce_history=True)
        train_keras_model.evaluate_model(model, dataset.x_train, dataset.y_train_labels, dataset.x_test, dataset.y_test_labels)
        train_scores = model.predict(dataset.x_train)
        hardness_score = train_scores[list(range(size_train)), dataset.y_train]
        res = np.asarray(sorted(range(len(hardness_score)), key=lambda k: hardness_score[k], reverse=True))
        with open(file_path_cache, "wb") as pick_file:
            pickle.dump(res, pick_file)
    return res


def order_by_same_network(dataset, model_lib, model_type, dropout_1_rate, dropout_2_rate,
                          reg_factor, bias_reg_factor, initial_lr, num_batchs,
                          batch_size, optimizer, lr_scheduler):
    model = model_lib.build_classifier_model(dataset, model_type=model_type,
                                             dropout_1_rate=dropout_1_rate, dropout_2_rate=dropout_2_rate,
                                             reg_factor=reg_factor,
                                             bias_reg_factor=bias_reg_factor)
    train_keras_model.compile_model(model, initial_lr=initial_lr,
                                    loss='categorical_crossentropy',
                                    optimizer=optimizer, metrics=['accuracy'])
    
    
    history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                    dataset.y_test_labels, num_batchs, verbose=True,
                                                    batch_size=batch_size,
                                                    initial_lr=initial_lr,
                                                    lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                    optimizer=optimizer, Compile=False,
                                                    model_output_path=None, metrics=['accuracy'])
    
#    output_path = "/cs/labs/daphna/guy.hacohen/project/models3/debug"
#    print('saving trained model to:', output_path)
#    histories = [history]
#    combined_history = histories[0].copy()
##            combined_history = {"loss": [], "acc": [], "val_loss": [], "val_acc": [], "std_acc": [], "std_val_acc": []}
#    for key in ["loss", "acc", "val_loss", "val_acc"]:
#        results = np.zeros((1, len(histories[0][key])))
#        for i in range(1):
#            results[i, :] = histories[i][key]
#        combined_history[key] = np.mean(results, axis=0)
#        if key == "acc":
#            combined_history["std_acc"] = scipy.stats.sem(results, axis=0)
#        if key == "val_acc":
#            combined_history["std_val_acc"] = scipy.stats.sem(results, axis=0)
#    with open(output_path + "_history", 'wb') as file_pi:
#        pickle.dump(combined_history, file_pi)

#    train_keras_model.evaluate_model(model, dataset.x_train, dataset.y_train_labels, dataset.x_test, dataset.y_test_labels)
    train_scores = model.predict(dataset.x_train)
    hardness_score = train_scores[list(range(size_train)), dataset.y_train]
    res = np.asarray(sorted(range(len(hardness_score)), key=lambda k: hardness_score[k], reverse=True))
    return res

def order_by_networks(dataset, network_list):
    size_train = len(dataset.y_train)
    scores = np.zeros_like(dataset.y_train_labels)
    for model in network_list:
        scores += model.predict(dataset.x_train)
    hardness_score = scores[list(range(size_train)), dataset.y_train]
    res = np.asarray(sorted(range(len(hardness_score)), key=lambda k: hardness_score[k], reverse=True))
    return res

def order_by_loss(dataset, model):
    size_train = len(dataset.y_train)
    scores = model.predict(dataset.x_train)
    hardness_score = scores[list(range(size_train)), dataset.y_train]
    res = np.asarray(sorted(range(len(hardness_score)), key=lambda k: hardness_score[k], reverse=True))
    return res

def balance_order(order, dataset):
    num_classes = dataset.n_classes
    size_each_class = dataset.x_train.shape[0] // num_classes
    class_orders = []
    for cls in range(num_classes):
        class_orders.append([i for i in range(len(order)) if dataset.y_train[order[i]] == cls])
    new_order = []
    ## take each group containing the next easiest image for each class,
    ## and putting them according to diffuclt-level in the new order
    for group_idx in range(size_each_class):
        group = sorted([class_orders[cls][group_idx] for cls in range(num_classes)])
        for idx in group:
            new_order.append(order[idx])
    return new_order


def balance_order1(order, num_classes, x_train, y_train):
    size_each_class = x_train.shape[0] // num_classes
    class_orders = []
    for cls in range(num_classes):
        class_orders.append([i for i in range(len(order)) if y_train[order[i]] == cls])
    new_order = []
    ## take each group containing the next easiest image for each class,
    ## and putting them according to diffuclt-level in the new order
    for group_idx in range(size_each_class):
        group = sorted([class_orders[cls][group_idx] for cls in range(num_classes)])
        for idx in group:
            new_order.append(order[idx])
    return new_order


def order_all_data_by_diffuclty(dataset_name,
                                diffuculty="easy"):
    """
    returns ordering on the dataset data, such that the last values of this
    order (i.e, the indexes for the test set) are set according to the
    diffuclty specified ("easy" means easy test set). the ordering is done
    via SVM on inception representation
    """
    
    
    if dataset_name.startswith('cifar100_subset'):
        superclass_idx = int(dataset_name[len("cifar100_subset_"):])
        dataset = cifar100_subset.Cifar100_Subset(supeclass_idx=superclass_idx,
                                                  normalize=False)

    elif dataset_name == "stl10":
        dataset = stl10.Stl10(normalize=False)

    network_name = "inception"
    (transfer_values_train, transfer_values_test) = transfer_learning.get_transfer_values_inception(dataset)


    all_transfer_values = np.concatenate((transfer_values_train, transfer_values_test), axis=0)
    all_x = np.concatenate((dataset.x_train, dataset.x_test), axis=0)
    all_y = np.concatenate((dataset.y_train, dataset.y_test), axis=0)

    
    train_scores, test_scores = transfer_learning.get_svm_scores(all_transfer_values, all_y,
                                                                 [], [], None,
                                                                 network_name="all_" + network_name,
                                                                 alternative_data_dir=dataset.data_dir)
    
    all_order = transfer_learning.rank_data_according_to_score(train_scores, all_y)
    class temp_datadet():
        n_classes = dataset.n_classes
        x_train = all_x
        y_train = all_y
    all_order = balance_order(all_order, temp_datadet)
    if diffuculty == "easy":
        test_idxs = all_order[:dataset.test_size]
        train_idxs = all_order[dataset.test_size:]
    elif diffuculty == "mid":
        mid = (len(all_order) - dataset.test_size) // 2
        test_idxs = all_order[mid:mid+dataset.test_size]
        train_idxs = np.concatenate((all_order[:mid], all_order[mid+dataset.test_size:]), axis=0)
    elif diffuculty == "hard":
        test_idxs = all_order[-dataset.test_size:]
        train_idxs = all_order[:-dataset.test_size]
    np.random.shuffle(test_idxs)
    np.random.shuffle(train_idxs)
    res_order = np.concatenate((train_idxs, test_idxs), axis=0)
    return res_order



def ensemble_expriment(dataset="cifar100_subset_16", model_type="large", dropout_1_rate=0.25, dropout_2_rate=0.5,
                       num_models=5, reg_factor=200e-4, bias_reg_factor=None, initial_lr=2e-3,
                       loss='categorical_crossentropy', optimizer="sgd", metrics=['accuracy'],
                       num_epochs=100, batch_size=100, verbose=True, test_each=50,
                       lr_scheduler="None", model_output_path=None,
                       data_function=train_keras_model.no_curriculum_data_function,
                       save_each=20):
    size_train = dataset.x_train.shape[0]
    num_batchs = (num_epochs * size_train) // batch_size

    for network in range(num_models):
        print("training network number: " + str(network))
        cur_path = model_output_path + "_net" + str(network)
        model = model_lib.build_classifier_model(dataset, model_type=model_type,
                                                 dropout_1_rate=dropout_1_rate, dropout_2_rate=dropout_2_rate,
                                                 reg_factor=reg_factor,
                                                 bias_reg_factor=bias_reg_factor)

        train_keras_model.compile_model(model, initial_lr=initial_lr,
                                        loss=loss,
                                        optimizer=optimizer, metrics=metrics)

        train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                              dataset.y_test_labels, num_batchs, verbose=verbose,
                                              batch_size=batch_size,
                                              test_each=test_each,
                                              initial_lr=initial_lr,
                                              lr_scheduler=lr_scheduler, loss=loss,
                                              optimizer=optimizer, Compile=False,
                                              model_output_path=cur_path, metrics=metrics,
                                              data_function=data_function,
                                              reduce_history=True,
                                              save_each=save_each)

    history = ensemble_models(save_each, num_models, model_output_path)
    return history


def ensemble_models(save_each, num_models, model_output_path, from_model=0, to_model=None):
    if to_model is None:
        to_model = num_models
    history = {"acc": [], "val_acc": [], "batch_num": []}

    for iter in range(0, num_batchs, save_each):
        start_time = time.time()
        print("calculating ensemble for batch: " + str(iter) + r"/" + str(num_batchs))
        res_test = np.zeros((dataset.test_size, dataset.n_classes))
        res_train = np.zeros((dataset.train_size, dataset.n_classes))
        for network in range(from_model, to_model):
            cur_model_path = model_output_path + "_net" + str(network) + "_iter" + str(iter)
            model = load_model(cur_model_path)
            res_test += model.predict(dataset.x_test)
            res_train += model.predict(dataset.x_train)
            with open(cur_model_path + "_res_test", 'wb') as file_pi:
                pickle.dump(res_test, file_pi)
            with open(cur_model_path + "_res_train", 'wb') as file_pi:
                pickle.dump(res_train, file_pi)
            del model
            gc.collect()
        predicted_train = np.argmax(res_train, axis=1)
        predicted_test = np.argmax(res_test, axis=1)

        history["acc"].append(np.mean(predicted_train == dataset.y_train))
        history["val_acc"].append(np.mean(predicted_test == dataset.y_test))
        history["batch_num"].append(iter)
        print("--- %s seconds ---" % (time.time() - start_time))
    return history


def get_ensemble_results_from_files(save_each, num_models, model_output_path, dataset):
    history = {"acc": [], "val_acc": [], "batch_num": []}
    for iter in range(0, num_batchs, save_each):
        start_time = time.time()
        print("calculating ensemble for batch: " + str(iter) + r"/" + str(num_batchs))
        res_test = np.zeros((dataset.test_size, dataset.n_classes))
        res_train = np.zeros((dataset.train_size, dataset.n_classes))
        for network in range(0, num_models):
            cur_model_path = model_output_path + "_net" + str(network) + "_iter" + str(iter)
            with open(cur_model_path + "_res_test", 'rb') as file_pi:
                results = pickle.load(file_pi)
                res_test += results
            with open(cur_model_path + "_res_train", 'rb') as file_pi:
                res_train += pickle.load(file_pi)
        predicted_train = np.argmax(res_train, axis=1)
        predicted_test = np.argmax(res_test, axis=1)

        history["acc"].append(np.mean(predicted_train == dataset.y_train))
        history["val_acc"].append(np.mean(predicted_test == dataset.y_test))
        history["batch_num"].append(iter)
        print("--- %s seconds ---" % (time.time() - start_time))
    return history


def ensemble_combined(save_each, num_to_combine):
    possible_orders = ['gad', 'model', "freq", "prototype", "vgg16", "vgg19", "inception", "xception", "resnet"]
    counter = 0
    num_combinations = len(list(itertools.combinations(possible_orders, num_to_combine)))
    for combination in itertools.combinations(possible_orders, num_to_combine):
        counter += 1
        print("in combination: " + str(counter) + r"/" + str(num_combinations))
        history = {"acc": [], "val_acc": [], "batch_num": []}
        for iter in range(0, num_batchs, save_each):
            start_time = time.time()
            print("calculating ensemble for batch: " + str(iter) + r"/" + str(num_batchs))
            res_test = np.zeros((dataset.test_size, dataset.n_classes))
            res_train = np.zeros((dataset.train_size, dataset.n_classes))
            for order in combination:
                cur_model_path = "models/ensemble_curriculum_adam_adap10_" + order + "_net0_iter" + str(iter)
                with open(cur_model_path + "_res_test", 'rb') as file_pi:
                    results = pickle.load(file_pi)
                    res_test += results
                with open(cur_model_path + "_res_train", 'rb') as file_pi:
                    res_train += pickle.load(file_pi)
            predicted_train = np.argmax(res_train, axis=1)
            predicted_test = np.argmax(res_test, axis=1)

            history["acc"].append(np.mean(predicted_train == dataset.y_train))
            history["val_acc"].append(np.mean(predicted_test == dataset.y_test))
            history["batch_num"].append(iter)
            print("--- %s seconds ---" % (time.time() - start_time))

        order_name = ""
        for order in combination:
            order_name += order + "_"
        history_output = "models/ensemble_curriculum_adam_" + order_name + "history"
        print('saving trained model to:', history_output)
        with open(history_output, 'wb') as file_pi:
            pickle.dump(history, file_pi)



# ensemble_vanilla_adam_adap10_${net}_repeat${i}_subset${subset}
def ensemble_repeats(model_output_path, networks, max_repeat, subsets, num_batchs, save_each, num_models, optimizer):

    for net_name in networks:
        for subset in subsets:
            dataset = cifar100_subset.Cifar100_Subset(supeclass_idx=subset)
            histories = {}
            for repeat in range(max_repeat):
                print("net: " + net_name + " subset: " + str(subset) + " repeat: " + str(repeat))
                print("----------------------------------------------")
                try:
                    cur_model_path = model_output_path + "_" + net_name + "_repeat" + str(repeat) + "_subset" + str(subset)
                    cur_history = get_ensemble_results_from_files(save_each, num_models, cur_model_path, dataset)
                    histories[repeat] = cur_history
                except:
                    continue
            if not histories:
                continue
            history = {"acc": [], "val_acc": [], "batch_num": [], "num_repeats": 0, "std_acc": [], "std_val_acc": []}
            history["batch_num"] = list(histories.values())[0]["batch_num"]
            for batch_idx in range(len(history["batch_num"])):
                curr_acc = []
                curr_val_acc = []
                for cur_history in histories.values():
                    curr_acc.append(cur_history["acc"][batch_idx])
                    curr_val_acc.append(cur_history["val_acc"][batch_idx])
                history["acc"].append(np.mean(curr_acc))
                history["val_acc"].append(np.mean(curr_val_acc))
                history["std_acc"].append(scipy.stats.sem(curr_acc))
                history["std_val_acc"].append(scipy.stats.sem(curr_val_acc))
            history["num_repeats"] = len(list(histories.keys()))

            if "vanilla" in model_output_path:
                expriment_type = "vanilla"
            elif "anti" in model_output_path:
                expriment_type = "anti"
            elif "random" in model_output_path:
                expriment_type = "random"
            elif "curriculum" in model_output_path:
                expriment_type = "curriculum"
            else:
                expriment_type = "bug"
            output_path = r"/cs/labs/daphna/guy.hacohen/project/models/histories/ensemble_history_" + optimizer + "_" + expriment_type + "_net_" + net_name + "_subset" + str(subset)
            if num_models != 10:
                output_path += "_models" + str(num_models)
            with open(output_path, 'wb') as file_pi:
                pickle.dump(history, file_pi)


    return


def data_function_from_input(curriculum, curriculum_scheduler, batch_size,
                             dataset, order, batch_increase,
                             increase_amount, starting_percent,
                             treshold, batch_increase_list=[]):
    if curriculum == "random":
        np.random.shuffle(order)
    if curriculum == "None" or curriculum == "vanilla":
        data_function = train_keras_model.no_curriculum_data_function
    elif curriculum in ["curriculum", "vanilla", "anti", "random"]:
        if curriculum_scheduler == "naive":
            data_function = naive_corriculum_data_function_generator(dataset, order, batch_size=batch_size)

        elif curriculum_scheduler == "adaptive":
            data_function = adaptive_corriculum_data_function_generator(dataset, order, batch_size=batch_size)
        
        elif curriculum_scheduler == "linear":
            data_function = linear_data_function_generator(dataset, order, batch_increase, increase_amount,
                                                           batch_size=batch_size)
        elif curriculum_scheduler == "exponent":
            data_function = exponent_data_function_generator(dataset, order, batch_increase, increase_amount,
                                                             starting_percent, batch_size=batch_size)
        elif curriculum_scheduler == "loss_tresh":
            data_function = exp_treshold_loss_data_function_generator(dataset, order, increase_amount,
                                                                      starting_percent, batch_size=batch_size,
                                                                      treshold=treshold)
        elif curriculum_scheduler == "partial":
            data_function = partial_data_function_generator(dataset, order,
                                                            starting_percent, batch_size=batch_size)
            
        elif curriculum_scheduler == "expo_adaptive":
            data_function = adaptive_expo_corriculum_data_function_generator(dataset, order,
                                                                             increase_amount, starting_percent,
                                                                             batch_size=batch_size, treshold=treshold)
        elif curriculum_scheduler == "single_step":
            data_function = single_step_data_function_generator(dataset, order,
                                                                batch_increase,
                                                                starting_percent)
        elif curriculum_scheduler == "exponent_jump_change":
            data_function = exponent_change_jumps_data_function_generator(dataset, order,
                                                                          batch_increase_list, increase_amount,
                                                                          starting_percent, batch_size=100)
        elif curriculum_scheduler == "exponent_change_2_jumps":
            data_function = exponent_data_change_2_first_function_generator(dataset, order,
                                                                            batch_increase,
                                                                            increase_amount, starting_percent,
                                                                            batch_size=100,
                                                                            first_jump=batch_increase_list[0],
                                                                            second_jump=batch_increase_list[1])
        else:
            print("unsupprted curriculum scheduler")
            raise ValueError
    elif curriculum == "self_pace" or curriculum == "anti_self_pace":
        anti_pace = False
        if curriculum == "anti_self_pace":
            anti_pace = True
        if curriculum_scheduler == "exponent":
            data_function = self_pace_exponent_data_function_generator(dataset, batch_increase, increase_amount,
                                                                       starting_percent, batch_size=batch_size,
                                                                       anti=anti_pace)
        else:
            print("unsupprted curriculum scheduler for self-pace")
            raise ValueError        
    else:
        print("unsupprted condition (not vanilla/curriculum/random/anti)")
        print("got the value:", curriculum)
        raise ValueError
    return data_function


def lr_schedule_from_input(lr_sched_arg,
                             dataset, batch_increase,
                             increase_amount, starting_percent,
                             treshold, lr_decay_rate, minimal_lr,
                             lr_batch_size, lr_decay_rate2, minimal_lr2,
                             lr_batch_size2, learning_rate, learning_rate2,
                             switch_lr_batch, cycle_min_lr, cycle_max_lr,
                             cycle_step_size, lr_change_arg):
    
    if lr_sched_arg == "None":
        
        lr_scheduler = train_keras_model.basic_lr_scheduler
    elif lr_sched_arg == "lr_sched1":
        lr_scheduler = decrease_lr_scheduler_generator(dataset)
    elif lr_sched_arg == "expo_lr_sched":
        lr_scheduler = expo_lr_scheduler_generator(batch_increase,
                                                   increase_amount,
                                                   starting_percent)
    elif lr_sched_arg == "expo_lr_sched_increase":
        lr_scheduler = expo_lr_scheduler_generator(batch_increase,
                                                   increase_amount,
                                                   starting_percent,
                                                   to_increase=True)
    elif lr_sched_arg == "loss_tresh":
        lr_scheduler = expo_loss_tresh_lr_scheduler_generator(batch_increase,
                                                              increase_amount,
                                                              starting_percent,
                                                              treshold=treshold)
    elif lr_sched_arg == "loss_tresh_increase":
        lr_scheduler = expo_loss_tresh_lr_scheduler_generator(batch_increase,
                                                              increase_amount,
                                                              starting_percent,
                                                              to_increase=True,
                                                              treshold=treshold)
    elif lr_sched_arg == "learn_lr":
        lr_scheduler = find_lr_generator()
        
    elif lr_sched_arg == "exponent_lr":
        print("here")
        lr_scheduler = exponent_decay_lr_generator(lr_decay_rate,
                                                   minimal_lr,
                                                   lr_batch_size)
    elif lr_sched_arg == "exponent_lr_combined":
        lr_scheduler = combine_exponent_decay_lr_generators(lr_decay_rate,
                                                            minimal_lr,
                                                            lr_batch_size,
                                                            lr_decay_rate2,
                                                            minimal_lr2,
                                                            lr_batch_size2,
                                                            learning_rate,
                                                            learning_rate2,
                                                            switch_lr_batch
                                                            )
    elif lr_sched_arg == "cycle_lr":
        lr_scheduler = cycle_lr_scheduler_generator(cycle_min_lr,
                                                    cycle_max_lr,
                                                    cycle_step_size,
                                                    lr_decay_rate,
                                                    lr_batch_size)
    else:
        print("unsupprted learning rate scheduler")
        raise ValueError
        
    if lr_change_arg == "None":
        pass
    elif lr_change_arg == "basic_ratio":
        lr_scheduler = change_lr_schedule_according_to_curriculum(lr_scheduler,
                                                                  dataset,
                                                                  basic_change_lr)
    elif lr_change_arg.startswith("exponent_ratio_"):
        exponent = float(lr_change_arg[len("exponent_ratio_"):])
        lr_scheduler = change_lr_schedule_according_to_curriculum(lr_scheduler,
                                                                  dataset,
                                                                  exponent_change_lr_generator(exponent))
    elif lr_change_arg.startswith("constant_"):
        const = float(lr_change_arg[len("constant_"):])
        lr_scheduler = change_lr_schedule_according_to_curriculum(lr_scheduler,
                                                                  dataset,
                                                                  constant_change_lr_generator(const))
    else:
        print("unsupprted change lr argument")
        raise ValueError
        
    return lr_scheduler


def get_cross_validation_indexes(dataset, num_folds):
    """
    gets dataset and number of folds, and return
    2 matrixes, train and test idxes.
    each matrix has num_folds rows, each row is a specific
    train set indexes or test set indexes of given fold.
    """
    indexes_path = os.path.join(dataset.data_dir, dataset.name + "_crossval_" + str(num_folds) + "_folds")
    if os.path.exists(indexes_path):
        with open(indexes_path, "rb") as input_file:
            train_idxes, test_idxes = pickle.load(input_file)
        return train_idxes, test_idxes
    else:
        data_size = dataset.test_size + dataset.train_size
        assert(data_size%num_folds == 0)
        new_data_order = list(range(data_size))
        np.random.shuffle(new_data_order)
        fold_size = data_size // num_folds
        train_idxes = np.zeros((num_folds, data_size - fold_size), dtype=np.int64)
        test_idxes = np.zeros((num_folds, fold_size), dtype=np.int64)
        for i, start_idx in enumerate(range(0, data_size, fold_size)):
            test_idx = new_data_order[start_idx:(start_idx+fold_size)]
            train_idx = new_data_order[:start_idx] + new_data_order[(start_idx+fold_size):]
            test_idxes[i, :] = test_idx
            train_idxes[i, :] = train_idx
        with open(indexes_path, "wb") as output_file:
            pickle.dump((train_idxes, test_idxes), output_file)
        return train_idxes, test_idxes


def get_cross_validation_indexes2(dataset):
    
    new_train_size = 2000
    new_val_size = 500
    new_test_size = 500

    indexes_path = os.path.join(dataset.data_dir, dataset.name + "_crossval_single_fold")
    if os.path.exists(indexes_path):
        with open(indexes_path, "rb") as input_file:
            train_idxes, val_idxes, test_idxes = pickle.load(input_file)
        return train_idxes, val_idxes, test_idxes
    
    else:
        all_y = np.concatenate((dataset.y_train, dataset.y_test), axis=0)
#        all_y = dataset.y_train
        size_each_class_train = new_train_size // dataset.n_classes
        size_each_class_val = new_val_size // dataset.n_classes
        size_each_class_test = new_test_size // dataset.n_classes
        
        train_idxes = []
        val_idxes = []
        test_idxes = []
        
        for cls in range(dataset.n_classes):
            cls_inxes = [i for i in range(len(all_y)) if all_y[i] == cls]
            np.random.shuffle(cls_inxes)
            train_idxes += cls_inxes[:size_each_class_train]
            val_idxes += cls_inxes[size_each_class_train:(size_each_class_train+size_each_class_val)]
            test_idxes += cls_inxes[-size_each_class_test:]
            
        np.random.shuffle(train_idxes)
        np.random.shuffle(val_idxes)
        np.random.shuffle(test_idxes)
        
        with open(indexes_path, "wb") as output_file:
            pickle.dump((train_idxes, val_idxes, test_idxes), output_file)
        return train_idxes, val_idxes, test_idxes



def reduce_order(order, train_idx, test_idx):
    new_order = np.array(order)[train_idx]
    
    for idx in sorted([order[i] for i in test_idx], reverse=True):
        new_order[new_order > idx] -= 1
    return new_order


def training_order_by_diffuclty(order, dataset, val_size, val_diffuculty="easy"):
    order_file = os.path.join(dataset.data_dir, val_diffuculty + "Val_train_order")
    if not os.path.exists(order_file):
        train_size = dataset.x_train.shape[0]
        test_size = dataset.x_test.shape[0]
        all_data_size = train_size + test_size
        test_idx = np.array(list(range(train_size, all_data_size)))
        
        if val_diffuculty == "easy":
            val_idx = order[:val_size]
        elif val_diffuculty == "mid":
            mid = (train_size - val_size) // 2 
            val_idx = order[mid:mid+val_size]
        elif val_diffuculty == "hard": 
            val_idx = order[-val_size:]
        train_idx = [i for i in range(train_size) if i not in val_idx]
        
        np.random.shuffle(train_idx)
        np.random.shuffle(val_idx)
            
        with open(order_file, 'wb+') as file_pi:
            pickle.dump((train_idx, val_idx, test_idx), file_pi)
    else:
        with open(order_file, 'rb+') as file_pi:
            (train_idx, val_idx, test_idx) = pickle.load(file_pi)
    return train_idx, val_idx, test_idx



def combine_orders_with_func(orders, order_func):
    return np.argsort(order_func([np.argsort(order) for order in orders]))

def combine_orders_max(*args):
    return combine_orders_with_func(args, lambda x: np.max(x, axis=0))

def combine_orders_min(*args):
    return combine_orders_with_func(args, lambda x: np.min(x, axis=0))

def combine_orders_sum(*args):
    return combine_orders_with_func(args, lambda x: np.sum(x, axis=0))


def combine_imagenet_networks(network_names, dataset,
                              combination_func=combine_orders_sum):
    orders = []
    for network_name in network_names:
        if network_name == "inception":
            (transfer_values_train, transfer_values_test) = transfer_learning.get_transfer_values_inception(dataset)
    
        else:
            (transfer_values_train, transfer_values_test) = transfer_learning.get_transfer_values_classic_networks(dataset,
                                                                                                                   network_name)
    
        train_scores, test_scores = transfer_learning.get_svm_scores(transfer_values_train, dataset.y_train,
                                                                     transfer_values_test, dataset.y_test, dataset,
                                                                     network_name=network_name)        
        order = transfer_learning.rank_data_according_to_score(train_scores, dataset.y_train)
        orders.append(order)
    return combination_func(*orders)

def svm_from_layers(dataset_to_classify, trained_model):
    
    inp = model.input                                           # input placeholder
    outputs = [layer.output for layer in model.layers]          # all layer outputs
    outputs = outputs[11:] # you can remove layers here
    functor = K.function([inp]+ [K.learning_phase()], outputs ) # evaluation function
    
    ## get output from each layer, without dropout (change to 1. for dropout)
    train_layer_outs = functor([dataset_to_classify.x_train, 0.])
    train_flat_layers = [np.reshape(layer, (layer.shape[0], np.prod(layer.shape[1:]))) for layer in train_layer_outs]
    print([layer.shape for layer in train_flat_layers])
    test_layer_outs = functor([dataset_to_classify.x_test, 0.])
    test_flat_layers = [np.reshape(layer, (layer.shape[0], np.prod(layer.shape[1:]))) for layer in test_layer_outs]

    accuracies = []
    for layer_idx in range(len(outputs)):
        print("in layer num:", layer_idx)
        clf = svm.SVC(probability=True)
        clf.fit(train_flat_layers[layer_idx], dataset_to_classify.y_train)
        
        test_scores = clf.predict_proba(test_flat_layers[layer_idx])
        test_accuracy = np.mean(np.argmax(test_scores, axis=1) == dataset_to_classify.y_test)
        print("accuracy", test_accuracy)
        accuracies.append((layer_idx, test_accuracy))
    return accuracies


def basic_change_lr(orig_lr, full_data_size, cur_data_size):
    return orig_lr * (cur_data_size / full_data_size)

def exponent_change_lr_generator(exponent):
    
    def exponent_change_lr(orig_lr, full_data_size, cur_data_size):
        return orig_lr * (cur_data_size**exponent / full_data_size**exponent)
    
    return exponent_change_lr

def constant_change_lr_generator(const):
    
    def constant_change_lr(orig_lr, full_data_size, cur_data_size):
        if cur_data_size >= full_data_size:
            return orig_lr
        else:
            return const
    
    return constant_change_lr



def change_lr_schedule_according_to_curriculum(lr_scheduler, dataset, change_lr_func):
    real_data_size = dataset.y_train.size
    
    def new_schedule_function(initial_lr, batch, history):
        original_lr = lr_scheduler(initial_lr, batch, history)
        if history and history["data_size"]:
            last_data_size = history["data_size"][-1]
        else:
            last_data_size = real_data_size
        new_lr = change_lr_func(original_lr, real_data_size, last_data_size)
        return new_lr
    
    return new_schedule_function


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='')
    # parser.add_argument("--generate_weights", default="False", help="dataset to use")
    parser.add_argument("--dataset", default="cifar100_subset_16", help="dataset to use")
    parser.add_argument("--data_size", default="all", help="reduces to number of training examples")
    parser.add_argument("--model_dir", default=r'../models3/', help="where to save the model")
    parser.add_argument("--experiment_name", default=r'curriculum_basic', help="which experiment to run")
    parser.add_argument("--output_name", default="", help="name of output file - will be added to model_dir")

    parser.add_argument("--verbose", default=True, type=bool, help="print more stuff")
    parser.add_argument("--net_type", default="large", help="network size ..")
    parser.add_argument("--optimizer", default="sgd", help="")
    parser.add_argument("--comp_grads", default="False", help="")
    parser.add_argument("--learning_rate", "-lr", default=2e-3, type=float)
    parser.add_argument("--l2_reg", default=50e-4, type=float)
    parser.add_argument("--bias_l2_reg", default=None, type=float)
    parser.add_argument("--dropout1", default=0.25, type=float)
    parser.add_argument("--dropout2", default=0.5, type=float)
    parser.add_argument("--curriculum", "-cl", default="curriculum")
    parser.add_argument("--curriculum_scheduler", default="adaptive")
    parser.add_argument("--batch_size", default=100, type=int)
    parser.add_argument("--num_epochs", default=100, type=int)
    parser.add_argument("--data_aug", default="False", help="augmentation")
    parser.add_argument("--exp", default=20, type=int)
    parser.add_argument("--rept", default=5, type=int)
    parser.add_argument("--lr_sched", default="None")
    parser.add_argument("--test_each", default=50, type=int, help="num batchs to run test-set after")
    parser.add_argument("--repeats", default=1, type=int, help="number of times to repeat the experiment")
    parser.add_argument("--save_each", default=None, type=int, help="numbers of batches before saving the model")
    parser.add_argument("--num_models", default=1, type=int, help="number of models in ensemble")
    parser.add_argument("--from_model", default=0, type=int)
    parser.add_argument("--to_model", default=None, type=int)
    parser.add_argument("--ranking_network", default="inception", help="network to rank curriculum by")
    parser.add_argument("--order", default="inception", help="determine the order of the examples")
    parser.add_argument("--experiment", default="train", help="which expriment to run")
    parser.add_argument("--momentum", default=0.0, type=float)
    parser.add_argument("--batch_increase", default=100, type=int)
    parser.add_argument("--increase_amount", default=0.1, type=float)
    parser.add_argument("--starting_percent", default=100/2500, type=float)
    parser.add_argument("--treshold", default=7.8, type=float)
    parser.add_argument("--balance", default=False, help="balance the ordering of the curriculum")
    
    parser.add_argument("--lr_decay_rate", default=10, type=float)
    parser.add_argument("--minimal_lr", default=1e-4, type=float)
    parser.add_argument("--lr_batch_size", default=300, type=int)
    parser.add_argument("--lr_decay_rate2", default=None, type=float)
    parser.add_argument("--minimal_lr2", default=None, type=float)
    parser.add_argument("--lr_batch_size2", default=None, type=int)
    parser.add_argument("--switch_lr_batch", default=750, type=float)
    parser.add_argument("--learning_rate2", "-lr2", default=None, type=float)
        
    parser.add_argument("--num_folds", default=10, type=int, help="number of folds in cross-validation")
    parser.add_argument("--num_boost", default=10, type=int, help="number of self ordering in boosting")
    parser.add_argument("--num_boots_repeats", default=5, type=int, help="number of of time to repeat each self ordering")
    parser.add_argument("--validation_hardness", default="None")
    parser.add_argument("--cross_val", default=False, help="to use the training set for cross_validation")
    parser.add_argument("--save_model", default=False)
    parser.add_argument("--svm_test_data", default="cifar100_subset_0")
    parser.add_argument("--cycle_min_lr", default=1e-5, type=float)
    parser.add_argument("--cycle_max_lr", default=1e-1, type=float)
    parser.add_argument("--cycle_step_size", default=8*(2500/100), type=int)
    parser.add_argument("--change_lr_for_curriculum", default="None")
    parser.add_argument('--batch_inc_list', nargs='+', help='list of jumps', default=[])
    
    

    
    args = parser.parse_args()
    
    batch_inc_list = [int(i) for i in args.batch_inc_list]
        
    if args.lr_decay_rate2 is None:
        args.lr_decay_rate2 = args.lr_decay_rate
    if args.lr_batch_size2 is None:
        args.lr_batch_size2 = args.lr_batch_size
    if args.learning_rate2 is None:
        args.learning_rate2 = args.learning_rate
    if args.minimal_lr2 is None:
        args.minimal_lr2 = args.minimal_lr
    
    if args.validation_hardness != "None":
        diffuclty = args.validation_hardness
        order_data = order_all_data_by_diffuclty(args.dataset, diffuclty)
        order_name = diffuclty
    else:
        order_data = None
        order_name = ""
        
        
    if args.momentum != 0.0 and not args.optimizer.endswith("sgd"):
        print(args.optimizer)
        print("cant use momentum with a non-sgd optimizer!")
        raise ValueError

    if args.data_size == 'all':
        smaller_data = False
    else:
        smaller_data = True

    if args.dataset.startswith('cifar100_subset'):
        superclass_idx = int(args.dataset[len("cifar100_subset_"):])
        if smaller_data:
            dataset = cifar100_subset.Cifar100_Subset(smaller_data_size=args.data_size, supeclass_idx=superclass_idx,
                                                      normalize=False, cross_val=args.cross_val,
                                                      order=order_data, order_name=order_name)
        else:
            dataset = cifar100_subset.Cifar100_Subset(supeclass_idx=superclass_idx,
                                                      normalize=False,
                                                      cross_val=args.cross_val,
                                                      order=order_data, order_name=order_name)
        model_lib = cifar100_model.Cifar100_Model()
    elif args.dataset.startswith('cifar100_validation_subset'):
        superclass_idx = int(args.dataset[len("cifar100_validation_subset_"):])
        dataset = cifar100_subset_validation.Cifar100_Subset_Validation(supeclass_idx=superclass_idx,
                                                                        normalize=False)
        model_lib = cifar100_model.Cifar100_Model()
    elif args.dataset.startswith('cifar100_custom_'):
        subsets_idxes = [int (idx) for idx in args.dataset[len("cifar100_custom_"):].split("_")]
        if smaller_data:
            dataset = cifar100_custom_subset.Cifar100_Custom_Subset(smaller_data_size=args.data_size,
                                                      normalize=False, subsets_idxes=subsets_idxes)
        else:
            dataset = cifar100_custom_subset.Cifar100_Custom_Subset(normalize=False,
                                                      subsets_idxes=subsets_idxes)
        model_lib = cifar100_model.Cifar100_Model()
    elif args.dataset == "cifar100":
        subsets_idxes = "all"
        if smaller_data:
            dataset = cifar100_custom_subset.Cifar100_Custom_Subset(smaller_data_size=args.data_size,
                                                      normalize=False, subsets_idxes=subsets_idxes)
        else:
            dataset = cifar100_custom_subset.Cifar100_Custom_Subset(normalize=False,
                                                      subsets_idxes=subsets_idxes)
        model_lib = cifar100_model.Cifar100_Model()
    elif args.dataset == "cifar10":
        if smaller_data:
            dataset = cifar10.Cifar10(smaller_data_size=args.data_size,
                                      normalize=False)
        else:
            dataset = cifar10.Cifar10(normalize=False)
        model_lib = cifar100_model.Cifar100_Model()
    elif args.dataset == "stl10":
        if smaller_data:
            dataset = stl10.Stl10(args.data_size, normalize=False)
        else:
            dataset = stl10.Stl10(normalize=False)
        model_lib = stl10_model.Stl10_Model()
    elif args.dataset == "squeezenet_imagenet_cats":
        dataset = imagenet_cats.Imagenet_cats(normalize=False)
        model_lib = squeezenet_model.SqueezeNet_Model()
    else:
        print("wrong dataset or datalib")
        raise ValueError

    model_dir = args.model_dir
    size_train = dataset.x_train.shape[0]
    num_batchs = (args.num_epochs * size_train) // args.batch_size

    lr_scheduler = lr_schedule_from_input(args.lr_sched,
                                          dataset, args.batch_increase,
                                          args.increase_amount, args.starting_percent,
                                          args.treshold, args.lr_decay_rate, args.minimal_lr,
                                          args.lr_batch_size, args.lr_decay_rate2, args.minimal_lr2,
                                          args.lr_batch_size2, args.learning_rate, args.learning_rate2,
                                          args.switch_lr_batch, args.cycle_min_lr, args.cycle_max_lr,
                                          args.cycle_step_size, args.change_lr_for_curriculum)

#    if (args.experiment == "schedule_cross_validation" or
#        args.experiment == "schedule_cross_validation_test"):
#        val_size = dataset.x_test.shape[0]
#        dataset.split_data_cross_validation([], "_all_data_in_train")
    normalized_flag = False
    classic_networks = ["vgg16", "vgg19", "inception", "xception", "resnet"]
    enhance_classic_networks = ["vgg16", "resnet", "inception"]
    if args.order in classic_networks:
        network_name = args.order
        if args.order == "inception":
            (transfer_values_train, transfer_values_test) = transfer_learning.get_transfer_values_inception(dataset)

        else:
            (transfer_values_train, transfer_values_test) = transfer_learning.get_transfer_values_classic_networks(dataset,
                                                                                                                   network_name)

        train_scores, test_scores = transfer_learning.get_svm_scores(transfer_values_train, dataset.y_train,
                                                                     transfer_values_test, dataset.y_test, dataset,
                                                                     network_name=network_name)
        order = transfer_learning.rank_data_according_to_score(train_scores, dataset.y_train)
        # print("dataset: " + dataset.name)
        # print("network: " + args.order)
        # print("svm train score:")
        # print(np.mean(np.argmax(train_scores, axis=1) == dataset.y_train))
        # print("svm test score:")
        # print(np.mean(np.argmax(test_scores, axis=1) == dataset.y_test))

    elif args.order == "gad":
        order = gad_order()
    elif args.order == "model":
        order = order_according_to_model(dataset, model_lib, args.net_type)
    elif args.order == "freq":
        order = order_by_freq(dataset)
    elif args.order == "prototype":
        order = order_by_prototype(dataset)
    elif args.order == "small_network":
        order = order_by_small_network(dataset, model_lib)
    elif args.order == "same_network":
        if not normalized_flag:
            dataset.normalize_dataset()
            normalized_flag = True
        order = order_by_same_network(dataset, model_lib, args.net_type, args.dropout1, args.dropout2,
                                      args.l2_reg, args.bias_l2_reg, args.learning_rate, num_batchs,
                                      args.batch_size, args.optimizer, lr_scheduler)
    elif args.order == "combined_all":
        order = combine_imagenet_networks(classic_networks, dataset)
    elif args.order == "combined_no_vgg":
        network_names = [name for name in classic_networks if not name.startswith("vgg")]
        order = combine_imagenet_networks(network_names, dataset)
    elif args.order == "combined_min":
        order = combine_imagenet_networks(enhance_classic_networks, dataset,
                                          combination_func=combine_orders_min)
    elif args.order == "combined_sum":
        order = combine_imagenet_networks(enhance_classic_networks, dataset,
                                          combination_func=combine_orders_sum)    
    elif args.order == "combined_max":
        order = combine_imagenet_networks(enhance_classic_networks, dataset,
                                          combination_func=combine_orders_max)
    else:
        print(args.order)
        print("wrong order input")
        raise ValueError
    
    if args.curriculum == "anti":
        order = np.flip(order, 0)
    elif args.curriculum == "random":
        np.random.shuffle(order)
    elif (args.curriculum in ["None", "curriculum", "vanilla", "self_pace",
                              "anti_self_pace"]):
        pass
    else:
        print(args.curriculum)
        print("bad curriculum value")
        raise ValueError

    if args.balance:
        order = balance_order(order, dataset)
        
    if not normalized_flag:
        dataset.normalize_dataset()
        normalized_flag = True

    # if args.experiment_name == "curriculum_basic":
    #     check_on_real_data('models/long_epochs_cifar_100_super' + str(superclass_idx),
    #                        batch_size=args.batch_size,
    #                        optimizer=args.optimizer, initial_lr=args.learning_rate, verbose=args.verbose,
    #                        test_each_epoch=args.test_each_epoch)
    #     history = curriculum_model('long_epochs_cifar100_curriculum_super' + str(superclass_idx),
    #                                batch_size=args.batch_size,
    #                                optimizer=args.optimizer,
    #                                initial_lr=args.learning_rate, verbose=args.verbose,
    #                                test_each_epoch=args.test_each_epoch)
    #     history = curriculum_model('long_epochs_cifar100_anticurriculum_super' + str(superclass_idx), anti_corriculum=True,
    #                                batch_size=args.batch_size,
    #                                optimizer=args.optimizer,
    #                                initial_lr=args.learning_rate, verbose=args.verbose,
    #                                test_each_epoch=args.test_each_epoch)
    #     history = curriculum_model('long_epochs_cifar100_random_super' + str(superclass_idx), random=True,
    #                                batch_size=args.batch_size,
    #                                optimizer=args.optimizer,
    #                                initial_lr=args.learning_rate, verbose=args.verbose,
    #                                test_each_epoch=args.test_each_epoch)

    if args.output_name:
        output_path = os.path.join(args.model_dir, args.output_name)
    else:
        output_path = None


    data_function = data_function_from_input(args.curriculum, args.curriculum_scheduler, args.batch_size,
                                             dataset, order, args.batch_increase,
                                             args.increase_amount, args.starting_percent,
                                             args.treshold, batch_inc_list)

    # history = ensemble_expriment(dataset=dataset, model_type=args.net_type, dropout_1_rate=args.dropout1,
    #                              dropout_2_rate=args.dropout2,
    #                              num_models=args.num_models, reg_factor=args.l2_reg, bias_reg_factor=args.bias_l2_reg,
    #                              initial_lr=args.learning_rate, optimizer=args.optimizer, num_epochs=args.num_epochs,
    #                              batch_size=args.batch_size, test_each=args.test_each,
    #                              lr_scheduler=lr_scheduler, model_output_path=output_path,
    #                              data_function=data_function,
    #                              save_each=args.save_each)

    # history = ensemble_models(args.save_each, args.num_models, output_path,
    #                           from_model=args.from_model, to_model=args.to_model)

    # ensemble_combined(args.save_each, 3)

    # history = get_ensemble_results_from_files(args.save_each, args.num_models, output_path)
    #
    #
    # if output_path is not None:
    #     history_output = output_path + "_nets" + str(args.num_models) + "_history"
    #     print('saving trained model to:', history_output)
    #     with open(history_output, 'wb') as file_pi:
    #         pickle.dump(history, file_pi)
    #
    # print(history)


    # # to ask daphna why the score is so good
    
    # train_scores, test_scores = transfer_learning.get_svm_scores(transfer_values_train, dataset.y_train,
    #                                                              transfer_values_test, dataset.y_test, dataset)
    # # print(np.argmax(train_scores, axis=1))
    # # print(dataset.y_train)
   
    # print("dataset: " + dataset.name)
    # print("network: " + args.order)
    # print("svm train score:")
    # print(np.mean(np.argmax(train_scores, axis=1) == dataset.y_train))
    # print("svm test score:")
    # print(np.mean(np.argmax(test_scores, axis=1) == dataset.y_test))
    
    
    # print(test_scores.shape)
    # print(train_scores.shape)
    if args.experiment == "train":
        start_time_all = time.time()
        histories =[]
        for repeat in range(args.repeats):
            model = model_lib.build_classifier_model(dataset, model_type=args.net_type,
                                                     dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                     reg_factor=args.l2_reg,
                                                     bias_reg_factor=args.bias_l2_reg)
        
            train_keras_model.compile_model(model, initial_lr=args.learning_rate,
                                            loss='categorical_crossentropy',
                                            optimizer=args.optimizer, metrics=['accuracy'],
                                            momentum=args.momentum)
        
            # history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
            #                                                 dataset.y_test_labels, num_batchs, verbose=args.verbose,
            #                                                 batch_size=args.batch_size,
            #                                                 test_each=args.test_each,
            #                                                 initial_lr=args.learning_rate,
            #                                                 lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
            #                                                 optimizer=args.optimizer, Compile=False,
            #                                                 model_output_path=None, metrics=['accuracy'],
            #                                                 data_function=data_function,
            #                                                 reduce_history=True,
            #                                                 save_each=args.save_each)
            
            history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                            dataset.y_test_labels, num_batchs, verbose=args.verbose,
                                                            batch_size=args.batch_size,
                                                            test_each=args.test_each,
                                                            initial_lr=args.learning_rate,
                                                            lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                            optimizer=args.optimizer, Compile=False,
                                                            model_output_path=output_path, metrics=['accuracy'],
                                                            data_function=data_function,
                                                            reduce_history=True,
                                                            save_each=args.save_each,
                                                            save_results=True,
                                                            net_num=repeat)
            histories.append(history)
        
        print("time all: --- %s seconds ---" % (time.time() - start_time_all))

        if output_path is not None:
            print('saving trained model to:', output_path)
            combined_history = histories[0].copy()
            for hist_idx in range(1,len(histories)):
                for key in ["loss", "acc", "val_loss", "val_acc"]:
                    combined_history[key] = np.asarray(combined_history[key]) + np.asarray(histories[hist_idx][key])
            for key in ["loss", "acc", "val_loss", "val_acc"]:
                combined_history[key] = combined_history[key] / len(histories)
            with open(output_path + "_history", 'wb') as file_pi:
                pickle.dump(combined_history, file_pi)

    elif args.experiment == "find_cycle_parameters":
        lr_scheduler = cycle_set_param_lr_scheduler_generator(args.cycle_min_lr,
                                                              args.cycle_max_lr,
                                                              num_batchs)
        start_time_all = time.time()
        histories =[]
        for repeat in range(args.repeats):
            data_function = data_function_from_input(args.curriculum, args.curriculum_scheduler, args.batch_size,
                                             dataset, order, args.batch_increase,
                                             args.increase_amount, args.starting_percent,
                                             args.treshold, batch_inc_list)
            print("starting repeat number: " + str(repeat))
            model = model_lib.build_classifier_model(dataset, model_type=args.net_type,
                                                     dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                     reg_factor=args.l2_reg,
                                                     bias_reg_factor=args.bias_l2_reg)
            train_keras_model.compile_model(model, initial_lr=args.learning_rate,
                                            loss='categorical_crossentropy',
                                            optimizer=args.optimizer, metrics=['accuracy'],
                                            momentum=args.momentum)
            history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                            dataset.y_test_labels, num_batchs, verbose=args.verbose,
                                                            batch_size=args.batch_size,
                                                            test_each=args.test_each,
                                                            initial_lr=args.learning_rate,
                                                            lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                            optimizer=args.optimizer, Compile=False,
                                                            metrics=['accuracy'],
                                                            data_function=data_function,
                                                            reduce_history=False,
                                                            save_each=args.save_each,
                                                            save_results=False,
                                                            net_num=repeat)

            histories.append(history)
            if output_path is not None:
                if args.save_model:
                    model.save(output_path + "_model_num"+str(repeat))
                    

        print("time all: --- %s seconds ---" % (time.time() - start_time_all))
        

        if output_path is not None:
            print('saving trained model to:', output_path)
            combined_history = histories[0].copy()
            for key in ["loss", "acc", "val_loss", "val_acc"]:
                results = np.zeros((args.repeats, len(histories[0][key])))
                for i in range(args.repeats):
                    results[i, :] = histories[i][key]
                combined_history[key] = np.mean(results, axis=0)
                if key == "acc":
                    combined_history["std_acc"] = scipy.stats.sem(results, axis=0)
                if key == "val_acc":
                    combined_history["std_val_acc"] = scipy.stats.sem(results, axis=0)
            with open(output_path + "_history", 'wb') as file_pi:
                pickle.dump(combined_history, file_pi)

        print(combined_history["loss"])

    elif args.experiment == "schedule":
        start_time_all = time.time()
        histories =[]
        for repeat in range(args.repeats):
            data_function = data_function_from_input(args.curriculum, args.curriculum_scheduler, args.batch_size,
                                             dataset, order, args.batch_increase,
                                             args.increase_amount, args.starting_percent,
                                             args.treshold, batch_inc_list)
            print("starting repeat number: " + str(repeat))
            model = model_lib.build_classifier_model(dataset, model_type=args.net_type,
                                                     dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                     reg_factor=args.l2_reg,
                                                     bias_reg_factor=args.bias_l2_reg)
            train_keras_model.compile_model(model, initial_lr=args.learning_rate,
                                            loss='categorical_crossentropy',
                                            optimizer=args.optimizer, metrics=['accuracy'],
                                            momentum=args.momentum)
            history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                            dataset.y_test_labels, num_batchs, verbose=args.verbose,
                                                            batch_size=args.batch_size,
                                                            test_each=args.test_each,
                                                            initial_lr=args.learning_rate,
                                                            lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                            optimizer=args.optimizer, Compile=False,
                                                            metrics=['accuracy'],
                                                            data_function=data_function,
                                                            reduce_history=False,
                                                            save_each=args.save_each,
                                                            save_results=False,
                                                            net_num=repeat)

            histories.append(history)
            if output_path is not None:
                if args.save_model:
                    model.save(output_path + "_model_num"+str(repeat))

        print("time all: --- %s seconds ---" % (time.time() - start_time_all))
        

        if output_path is not None:
            print('saving trained model to:', output_path)
            combined_history = histories[0].copy()
            for key in ["loss", "acc", "val_loss", "val_acc"]:
                results = np.zeros((args.repeats, len(histories[0][key])))
                for i in range(args.repeats):
                    results[i, :] = histories[i][key]
                combined_history[key] = np.mean(results, axis=0)
                if key == "acc":
                    combined_history["std_acc"] = scipy.stats.sem(results, axis=0)
                if key == "val_acc":
                    combined_history["std_val_acc"] = scipy.stats.sem(results, axis=0)
            with open(output_path + "_history", 'wb') as file_pi:
                pickle.dump(combined_history, file_pi)
#            if args.save_model:
#                model.save(output_path)
        print(combined_history["loss"])

    elif args.experiment == "schedule_bootstrap":
        start_time_all = time.time()
        histories_all_boosts =[[] for i in range(args.num_boost + 1)]
        for repeat in range(args.repeats):
            print("starting repeat number: " + str(repeat))
            models_old_order = []
            for boost_num in range(args.num_boost + 1):
                if not models_old_order:
                    scheduling = "vanilla"
                    lr_scheduler = lr_schedule_from_input(args.lr_sched,
                                                          dataset, args.batch_increase,
                                                          args.increase_amount, args.starting_percent,
                                                          args.treshold, args.lr_decay_rate2, args.minimal_lr2,
                                                          args.lr_batch_size2, args.lr_decay_rate2, args.minimal_lr2,
                                                          args.lr_batch_size2, args.learning_rate2, args.learning_rate2,
                                                          args.switch_lr_batch, args.cycle_min_lr, args.cycle_max_lr,
                                                          args.cycle_step_size, args.change_lr_for_curriculum)
                    initial_lr = args.learning_rate2
#                    np.random.shuffle(order)
                else:
                    scheduling = "curriculum"
                    orders = [order_by_networks(dataset, [model]) for model in models_old_order]
                    if args.order == "combined_min":
                        order = combine_orders_min(*orders)
                        
                    elif args.order == "combined_sum":
                        order = combine_orders_sum(*orders)
                        
                    elif args.order == "combined_max":
                        order = combine_orders_max(*orders)
                    else:
                        print("order:", args.order, "not supported in bootstaping")
                        raise ValueError
                    
                    order = balance_order(order, dataset)
                    lr_scheduler = lr_schedule_from_input(args.lr_sched,
                                                          dataset, args.batch_increase,
                                                          args.increase_amount, args.starting_percent,
                                                          args.treshold, args.lr_decay_rate, args.minimal_lr,
                                                          args.lr_batch_size, args.lr_decay_rate2, args.minimal_lr2,
                                                          args.lr_batch_size2, args.learning_rate, args.learning_rate2,
                                                          args.switch_lr_batch, args.cycle_min_lr, args.cycle_max_lr,
                                                          args.cycle_step_size, args.change_lr_for_curriculum)
                    initial_lr = args.learning_rate
                    
                models_for_new_order = []
                for boost_repeat in range(args.num_boots_repeats):
                    data_function = data_function_from_input(scheduling, args.curriculum_scheduler, args.batch_size,
                                                             dataset, order, args.batch_increase,
                                                             args.increase_amount, args.starting_percent,
                                                             args.treshold, batch_inc_list)
                    
                    order_model = model_lib.build_classifier_model(dataset, model_type=args.net_type,
                                                                   dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                                   reg_factor=args.l2_reg,
                                                                   bias_reg_factor=args.bias_l2_reg)
                    
                    train_keras_model.compile_model(order_model, initial_lr=initial_lr,
                                                    loss='categorical_crossentropy',
                                                    optimizer=args.optimizer, metrics=['accuracy'],
                                                    momentum=args.momentum)
                    
                    history = train_keras_model.train_model_batches(order_model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                                    dataset.y_test_labels, num_batchs, verbose=args.verbose,
                                                                    batch_size=args.batch_size,
                                                                    test_each=args.test_each,
                                                                    initial_lr=initial_lr,
                                                                    lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                                    optimizer=args.optimizer, Compile=False,
                                                                    metrics=['accuracy'],
                                                                    data_function=data_function,
                                                                    reduce_history=False,
                                                                    save_each=args.save_each,
                                                                    save_results=False,
                                                                    net_num=repeat)                                        

                    models_for_new_order.append(order_model)
                    histories_all_boosts[boost_num].append(history)
                models_old_order = models_for_new_order
                
                

        print("time all: --- %s seconds ---" % (time.time() - start_time_all))
        
        if output_path is not None:
            print('saving trained model to:', output_path)
            for boost_num, histories in enumerate(histories_all_boosts):
                print(len(histories))
                combined_history = histories[0].copy()
                for key in ["loss", "acc", "val_loss", "val_acc"]:
                    results = np.zeros((args.repeats, len(histories[0][key])))
                    for i in range(args.repeats):
                        results[i, :] = histories[i][key]
                    combined_history[key] = np.mean(results, axis=0)
                    if key == "acc":
                        combined_history["std_acc"] = scipy.stats.sem(results, axis=0)
                    if key == "val_acc":
                        combined_history["std_val_acc"] = scipy.stats.sem(results, axis=0)
                with open(output_path + "_history_boost" + str(boost_num), 'wb') as file_pi:
                    pickle.dump(combined_history, file_pi)
                if args.save_model:
                    model.save(output_path)
#                print(combined_history["loss"])

    elif args.experiment == "svm_layers":
        data_function = data_function_from_input(args.curriculum, args.curriculum_scheduler, args.batch_size,
                                         dataset, order, args.batch_increase,
                                         args.increase_amount, args.starting_percent,
                                         args.treshold, batch_inc_list)
        model = model_lib.build_classifier_model(dataset, model_type=args.net_type,
                                                 dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                 reg_factor=args.l2_reg,
                                                 bias_reg_factor=args.bias_l2_reg)
        train_keras_model.compile_model(model, initial_lr=args.learning_rate,
                                        loss='categorical_crossentropy',
                                        optimizer=args.optimizer, metrics=['accuracy'],
                                        momentum=args.momentum)
        history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                        dataset.y_test_labels, num_batchs, verbose=args.verbose,
                                                        batch_size=args.batch_size,
                                                        test_each=args.test_each,
                                                        initial_lr=args.learning_rate,
                                                        lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                        optimizer=args.optimizer, Compile=False,
                                                        metrics=['accuracy'],
                                                        data_function=data_function,
                                                        reduce_history=False,
                                                        save_each=args.save_each,
                                                        save_results=False)
        
        if output_path is not None:
            if args.save_model:
                print("saving model...")
                model.save(output_path)
        
        if args.svm_test_data.startswith('cifar100_subset'):
            superclass_idx = int(args.svm_test_data[len("cifar100_subset_"):])
            test_dataset = cifar100_subset.Cifar100_Subset(supeclass_idx=superclass_idx)
        else:
            print("currently svm_test_data supports only cifar100 subesets")
            raise ValueError
        accuracies = svm_from_layers(test_dataset, model)
        
        if output_path is not None:
            print('saving trained model to:', output_path)
            with open(output_path + "_svm_layers", 'wb') as file_pi:
                pickle.dump(accuracies, file_pi)
        print(accuracies)

    elif args.experiment == "create_random_orders":
        while True:
            index_path = os.path.join(args.model_dir, "index")
            if os.path.exists(index_path):
                with open(index_path, 'rb') as file_pi:
                    order_idx = pickle.load(file_pi) + 1
            else:
                order_idx = 0
            
            output_path = os.path.join(args.model_dir, "random" + str(order_idx))
            
            start_time_all = time.time()
            histories =[]
            for repeat in range(args.repeats):
                print("starting order idx number:", order_idx)
                np.random.shuffle(order)
                data_function = data_function_from_input(args.curriculum, args.curriculum_scheduler, args.batch_size,
                                                 dataset, order, args.batch_increase,
                                                 args.increase_amount, args.starting_percent,
                                                 args.treshold, batch_inc_list)
                print("starting repeat number: " + str(repeat))
                model = model_lib.build_classifier_model(dataset, model_type=args.net_type,
                                                         dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                         reg_factor=args.l2_reg,
                                                         bias_reg_factor=args.bias_l2_reg)
                train_keras_model.compile_model(model, initial_lr=args.learning_rate,
                                                loss='categorical_crossentropy',
                                                optimizer=args.optimizer, metrics=['accuracy'],
                                                momentum=args.momentum)
                history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                                dataset.y_test_labels, num_batchs, verbose=args.verbose,
                                                                batch_size=args.batch_size,
                                                                test_each=args.test_each,
                                                                initial_lr=args.learning_rate,
                                                                lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                                optimizer=args.optimizer, Compile=False,
                                                                metrics=['accuracy'],
                                                                data_function=data_function,
                                                                reduce_history=False,
                                                                save_each=args.save_each,
                                                                save_results=False,
                                                                net_num=repeat)
                histories.append(history)
    
            print("time all: --- %s seconds ---" % (time.time() - start_time_all))
            
                  
            if output_path is not None:
                print('saving trained model to:', output_path)
                combined_history = histories[0].copy()
        #            combined_history = {"loss": [], "acc": [], "val_loss": [], "val_acc": [], "std_acc": [], "std_val_acc": []}
                for key in ["loss", "acc", "val_loss", "val_acc"]:
                    results = np.zeros((args.repeats, len(histories[0][key])))
                    for i in range(args.repeats):
                        results[i, :] = histories[i][key]
                    combined_history[key] = np.mean(results, axis=0)
                    if key == "acc":
                        combined_history["std_acc"] = scipy.stats.sem(results, axis=0)
                    if key == "val_acc":
                        combined_history["std_val_acc"] = scipy.stats.sem(results, axis=0)
                with open(output_path + "_history", 'wb') as file_pi:
                    pickle.dump(combined_history, file_pi)
                with open(output_path + "_order", 'wb') as file_pi:
                    pickle.dump(order, file_pi)
                with open(index_path, 'wb') as file_pi:
                    pickle.dump(order_idx, file_pi)
            print(combined_history["loss"])

    elif args.experiment == "boosting":
        start_time_all = time.time()
        histories =[]
        for repeat in range(args.repeats):
            print("starting repeat number: " + str(repeat))
            cur_order = order
            last_model = None
            for boost in range(args.num_boost):
                if boost != 0:
                    cur_order = order_according_to_trained_model(last_model, dataset)
                    if args.curriculum == "anti":
                        cur_order = np.flip(cur_order, 0)
                    elif args.curriculum == "random":
                        np.random.shuffle(cur_order)
                    if args.balance:
                        cur_order = balance_order(cur_order, dataset)
                
                data_function = data_function_from_input(args.curriculum, args.curriculum_scheduler, args.batch_size,
                                                 dataset, order, args.batch_increase,
                                                 args.increase_amount, args.starting_percent,
                                                 args.treshold, batch_inc_list)
                
                model = model_lib.build_classifier_model(dataset, model_type=args.net_type,
                                                         dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                         reg_factor=args.l2_reg,
                                                         bias_reg_factor=args.bias_l2_reg)
                train_keras_model.compile_model(model, initial_lr=args.learning_rate,
                                                loss='categorical_crossentropy',
                                                optimizer=args.optimizer, metrics=['accuracy'],
                                                momentum=args.momentum)
                history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                                dataset.y_test_labels, num_batchs, verbose=args.verbose,
                                                                batch_size=args.batch_size,
                                                                test_each=args.test_each,
                                                                initial_lr=args.learning_rate,
                                                                lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                                optimizer=args.optimizer, Compile=False,
                                                                metrics=['accuracy'],
                                                                data_function=data_function,
                                                                reduce_history=False,
                                                                save_each=args.save_each,
                                                                save_results=False,
                                                                net_num=repeat)
                last_model = model
                if boost == (args.num_boost - 1):
                    histories.append(history)

        print("time all: --- %s seconds ---" % (time.time() - start_time_all))
        
        if output_path is not None:
            print('saving trained model to:', output_path)
            combined_history = histories[0].copy()
            for key in ["loss", "acc", "val_loss", "val_acc"]:
                results = np.zeros((args.repeats, len(histories[0][key])))
                for i in range(args.repeats):
                    results[i, :] = histories[i][key]
                combined_history[key] = np.mean(results, axis=0)
                if key == "acc":
                    combined_history["std_acc"] = scipy.stats.sem(results, axis=0)
                if key == "val_acc":
                    combined_history["std_val_acc"] = scipy.stats.sem(results, axis=0)
            with open(output_path + "_history", 'wb') as file_pi:
                pickle.dump(combined_history, file_pi)
        print(combined_history["loss"])
    
    elif args.experiment == "schedule_cross_validation2":
        
        train_size = 2000
        test_size = 500
        val_size = 500
#        
#        train_idxes, test_idxes = get_cross_validation_indexes(dataset, args.num_folds)
#        train_idx = train_idxes[0, :]
#        test_idx = test_idxes[0, :]
        
#        train_idx, val_idx, test_idx = get_cross_validation_indexes2(dataset)
#        test_idx = list(range(train_size + val_size, train_size + val_size + test_size))

        if args.dataset.startswith('cifar100_subset'):
            val_dataset = cifar100_subset.Cifar100_Subset(supeclass_idx=superclass_idx, normalize=True)
        elif args.dataset == "stl10":
            val_dataset = stl10.Stl10(normalize=True)

        if args.validation_hardness == "None":

            train_order_file = os.path.join(dataset.data_dir, "shuffled_train_order")
            if not os.path.exists(train_order_file):
                shuffle_idxes = list(range(2500))
                np.random.shuffle(shuffle_idxes)
                shuffle_idxes = balance_order(shuffle_idxes, dataset)
                with open(train_order_file, 'wb+') as file_pi:
                    pickle.dump(shuffle_idxes, file_pi)
            else:
                with open(train_order_file, 'rb+') as file_pi:
                    shuffle_idxes = pickle.load(file_pi)
            train_idx = np.array(shuffle_idxes)
            val_idx = []
            test_idx = np.array(list(range(2500, 3000)))
        elif args.validation_hardness == "easy":
            train_idx, val_idx, test_idx = training_order_by_diffuclty(order, val_dataset, val_size, val_diffuculty="easy")
        elif args.validation_hardness == "mid":
            train_idx, val_idx, test_idx = training_order_by_diffuclty(order, val_dataset, val_size, val_diffuculty="mid")
        elif args.validation_hardness == "hard":
            train_idx, val_idx, test_idx = training_order_by_diffuclty(order, val_dataset, val_size, val_diffuculty="hard")
        else:
            print("validation hardness level got illegal input!")
            raise ValueError
        
            

        
        all_x = np.concatenate((val_dataset.x_train, val_dataset.x_test), axis=0)
        all_y = np.concatenate((val_dataset.y_train, val_dataset.y_test), axis=0)
        all_y_labels = np.concatenate((val_dataset.y_train_labels, val_dataset.y_test_labels), axis=0)
        all_scores = np.concatenate((train_scores, test_scores), axis=0)
        
        all_order = transfer_learning.rank_data_according_to_score(all_scores, all_y)        
        
        all_order = balance_order1(all_order, dataset.n_classes, all_x, all_y)
        
        all_idxes = np.concatenate((train_idx, val_idx, test_idx), axis=0)
        all_idxes = [int(i) for i in all_idxes]
        all_x = all_x[all_idxes, :, :, :]
        all_y = all_y[all_idxes]
        all_y_labels = all_y_labels[all_idxes, :]
        new_train_idxes = list(range(train_size))
        new_val_idxes = list(range(train_size, train_size + val_size))
        new_test_idxes = list(range(train_size + val_size, train_size + val_size + test_size))
        
        
        all_order = np.argsort(all_idxes)[np.array(all_order)]
        order = np.array([i for i in all_order if i < train_size])

        
        val_dataset.x_train = all_x[new_train_idxes, :, :, :]
        val_dataset.x_test = all_x[new_val_idxes, :, :, :]
        val_dataset.y_train = all_y[new_train_idxes]
        val_dataset.y_test = all_y[new_val_idxes]
        val_dataset.y_train_labels = all_y_labels[new_train_idxes, :]
        val_dataset.y_test_labels = all_y_labels[new_val_idxes, :]

        order = balance_order(order, val_dataset)

        if args.curriculum == "anti":
            order = np.flip(order, 0)
        elif args.curriculum == "random":
            np.random.shuffle(order)        
        start_time_all = time.time()
        histories =[]
        for repeat in range(args.repeats):
            data_function = data_function_from_input(args.curriculum, args.curriculum_scheduler, args.batch_size,
                                             val_dataset, order, args.batch_increase,
                                             args.increase_amount, args.starting_percent,
                                             args.treshold, batch_inc_list)
            print("starting repeat number:", repeat) 
            model = model_lib.build_classifier_model(val_dataset, model_type=args.net_type,
                                                     dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                     reg_factor=args.l2_reg,
                                                     bias_reg_factor=args.bias_l2_reg)
            train_keras_model.compile_model(model, initial_lr=args.learning_rate,
                                            loss='categorical_crossentropy',
                                            optimizer=args.optimizer, metrics=['accuracy'],
                                            momentum=args.momentum)
            history = train_keras_model.train_model_batches(model, val_dataset.x_train, val_dataset.y_train_labels, val_dataset.x_test,
                                                            val_dataset.y_test_labels, num_batchs, verbose=args.verbose,
                                                            batch_size=args.batch_size,
                                                            test_each=args.test_each,
                                                            initial_lr=args.learning_rate,
                                                            lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                            optimizer=args.optimizer, Compile=False,
                                                            metrics=['accuracy'],
                                                            data_function=data_function,
                                                            reduce_history=False,
                                                            save_each=args.save_each,
                                                            save_results=False,
                                                            net_num=repeat)
            histories.append(history)
    
        print("time all: --- %s seconds ---" % (time.time() - start_time_all))
              
        if output_path is not None:
            print('saving trained model to:', output_path)
            combined_history = histories[0].copy()
#            combined_history = {"loss": [], "acc": [], "val_loss": [], "val_acc": [], "std_acc": [], "std_val_acc": []}
            for key in ["loss", "acc", "val_loss", "val_acc"]:
                results = np.zeros((args.repeats, len(histories[0][key])))
                for i in range(args.repeats):
                    results[i, :] = histories[i][key]
                combined_history[key] = np.mean(results, axis=0)
                if key == "acc":
                    combined_history["std_acc"] = scipy.stats.sem(results, axis=0)
                if key == "val_acc":
                    combined_history["std_val_acc"] = scipy.stats.sem(results, axis=0)
            with open(output_path + "_history", 'wb') as file_pi:
                pickle.dump(combined_history, file_pi)
            print(combined_history["loss"])

    elif args.experiment == "schedule_cross_validation_test":
        train_size = 2500
        test_size = 500
        train_idx, val_idx, test_idx = get_cross_validation_indexes2(dataset)
    
        if args.dataset.startswith('cifar100_subset'):
            test_dataset = cifar100_subset.Cifar100_Subset(supeclass_idx=superclass_idx, normalize=True)
        elif args.dataset == "stl10":
            test_dataset = stl10.Stl10(normalize=True)
        
        all_x = np.concatenate((test_dataset.x_train, test_dataset.x_test), axis=0)
        all_y = np.concatenate((test_dataset.y_train, test_dataset.y_test), axis=0)
        all_y_labels = np.concatenate((test_dataset.y_train_labels, test_dataset.y_test_labels), axis=0)
        all_scores = np.concatenate((train_scores, test_scores), axis=0)
        
        all_order = transfer_learning.rank_data_according_to_score(all_scores, all_y)
        
        if args.curriculum == "anti":
            all_order = np.flip(all_order, 0)
        elif args.curriculum == "random":
            np.random.shuffle(all_order)
        
        all_order = balance_order1(all_order, dataset.n_classes, all_x, all_y)
        
        
        
        
        all_idxes = np.concatenate((train_idx, val_idx, test_idx), axis=0)
        all_idxes = [int(i) for i in all_idxes]
        all_x = all_x[all_idxes, :, :, :]
        all_y = all_y[all_idxes]
        all_y_labels = all_y_labels[all_idxes, :]
        new_train_idxes = list(range(train_size))
        new_test_idxes = list(range(train_size, train_size + test_size))
        
        
        all_order = np.argsort(all_idxes)[np.array(all_order)]
        order = np.array([i for i in all_order if i < train_size])

        
        test_dataset.x_train = all_x[new_train_idxes, :, :, :]
        test_dataset.x_test = all_x[new_test_idxes, :, :, :]
        test_dataset.y_train = all_y[new_train_idxes]
        test_dataset.y_test = all_y[new_test_idxes]
        test_dataset.y_train_labels = all_y_labels[new_train_idxes, :]
        test_dataset.y_test_labels = all_y_labels[new_test_idxes, :]

        order = balance_order(order, test_dataset)
        
        
        start_time_all = time.time()
        histories =[]
        for repeat in range(args.repeats):
            data_function = data_function_from_input(args.curriculum, args.curriculum_scheduler, args.batch_size,
                                             test_dataset, order, args.batch_increase,
                                             args.increase_amount, args.starting_percent,
                                             args.treshold, batch_inc_list)
            print("starting repeat number:", repeat) 
            model = model_lib.build_classifier_model(test_dataset, model_type=args.net_type,
                                                     dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                     reg_factor=args.l2_reg,
                                                     bias_reg_factor=args.bias_l2_reg)
            train_keras_model.compile_model(model, initial_lr=args.learning_rate,
                                            loss='categorical_crossentropy',
                                            optimizer=args.optimizer, metrics=['accuracy'],
                                            momentum=args.momentum)
            history = train_keras_model.train_model_batches(model, test_dataset.x_train, test_dataset.y_train_labels,
                                                            test_dataset.x_test,
                                                            test_dataset.y_test_labels, num_batchs, verbose=args.verbose,
                                                            batch_size=args.batch_size,
                                                            test_each=args.test_each,
                                                            initial_lr=args.learning_rate,
                                                            lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                            optimizer=args.optimizer, Compile=False,
                                                            metrics=['accuracy'],
                                                            data_function=data_function,
                                                            reduce_history=False,
                                                            save_each=args.save_each,
                                                            save_results=False,
                                                            net_num=repeat)
            histories.append(history)
    
        print("time all: --- %s seconds ---" % (time.time() - start_time_all))
              
        if output_path is not None:
            print('saving trained model to:', output_path)
            combined_history = histories[0].copy()
#            combined_history = {"loss": [], "acc": [], "val_loss": [], "val_acc": [], "std_acc": [], "std_val_acc": []}
            for key in ["loss", "acc", "val_loss", "val_acc"]:
                results = np.zeros((args.repeats, len(histories[0][key])))
                for i in range(args.repeats):
                    results[i, :] = histories[i][key]
                combined_history[key] = np.mean(results, axis=0)
                if key == "acc":
                    combined_history["std_acc"] = scipy.stats.sem(results, axis=0)
                if key == "val_acc":
                    combined_history["std_val_acc"] = scipy.stats.sem(results, axis=0)
            with open(output_path + "_history", 'wb') as file_pi:
                pickle.dump(combined_history, file_pi)
            print(combined_history["loss"])
    
    
    
    
    elif args.experiment == "debug":

         start_time = time.time()
         model = model_lib.build_classifier_model(dataset, model_type="large",
                                                  dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                  reg_factor=args.l2_reg,
                                                  bias_reg_factor=args.bias_l2_reg)

         train_keras_model.compile_model(model, initial_lr=args.learning_rate,
                                         loss='categorical_crossentropy',
                                         optimizer=args.optimizer, metrics=['accuracy'])

         history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                         dataset.y_test_labels, num_batchs, verbose=True,
                                                         batch_size=args.batch_size,
                                                         test_each=args.test_each,
                                                         initial_lr=args.learning_rate,
                                                         lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                         optimizer=args.optimizer, Compile=False,
                                                         model_output_path=None, metrics=['accuracy'],
                                                         data_function=data_function,
                                                         reduce_history=True,
                                                         save_each=args.save_each)
         print("large: --- %s seconds ---" % (time.time() - start_time))
         print(model.summary())
         train_keras_model.evaluate_model(model, dataset.x_train, dataset.y_train_labels, dataset.x_test, dataset.y_test_labels)
         print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
         print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
         print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
         print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
         start_time = time.time()
         model = model_lib.build_classifier_model(dataset, model_type="small",
                                                  dropout_1_rate=args.dropout1, dropout_2_rate=args.dropout2,
                                                  reg_factor=args.l2_reg,
                                                  bias_reg_factor=args.bias_l2_reg)

         train_keras_model.compile_model(model, initial_lr=args.learning_rate,
                                         loss='categorical_crossentropy',
                                         optimizer=args.optimizer, metrics=['accuracy'])

         history = train_keras_model.train_model_batches(model, dataset.x_train, dataset.y_train_labels, dataset.x_test,
                                                         dataset.y_test_labels, num_batchs, verbose=True,
                                                         batch_size=args.batch_size,
                                                         test_each=args.test_each,
                                                         initial_lr=args.learning_rate,
                                                         lr_scheduler=lr_scheduler, loss='categorical_crossentropy',
                                                         optimizer=args.optimizer, Compile=False,
                                                         model_output_path=None, metrics=['accuracy'],
                                                         data_function=data_function,
                                                         reduce_history=True,
                                                         save_each=args.save_each)
         print("small: --- %s seconds ---" % (time.time() - start_time))
         train_keras_model.evaluate_model(model, dataset.x_train, dataset.y_train_labels, dataset.x_test, dataset.y_test_labels)
         print(model.summary())
    # if output_path is not None:
    #     print('saving trained model to:', output_path)
    #     combined_history = histories[0].copy()
    #     for hist_idx in range(1,len(histories)):
    #         for key in ["loss", "acc", "val_loss", "val_acc"]:
    #             combined_history[key] = np.asarray(combined_history[key]) + np.asarray(histories[hist_idx][key])
    #     for key in ["loss", "acc", "val_loss", "val_acc"]:
    #         combined_history[key] = combined_history[key] / len(histories)
    #     with open(output_path + "_history", 'wb') as file_pi:
    #         pickle.dump(combined_history, file_pi)

    elif args.experiment == "ensemble_models":
        max_repeat = 8
        # networks = ["inception", "resnet", "inception", "xception", "vgg16", "vgg19", "gad", "models", "prototype", "freq"]
        # networks = ["inception", "freq", "small_network", "same_network"]
        # networks = ["small_network"]
        # networks = ["inception"]
        # networks = ["freq"]
        networks = ["same_network"]
        subsets = [0, 4, 7, 14, 16]
        # networks = ["inception"]
        # subsets = [args.exp]
        # print(args.dataset)
        # print(dataset.superclass_idx)
        # print(dataset.y_train[:9])
        # print(dataset.y_test[:9])
        # draw_results.plot_cifar_100(dataset.x_train)
        # draw_results.plot_cifar_100(dataset.x_test)
        ensemble_repeats(output_path, networks, max_repeat, subsets, num_batchs, args.save_each, args.num_models, args.optimizer)











    # num_models = 5
    # early_stop_epoch = 10

    # x_train, y_train, y_train_labels = dataset.load_training_data()
    # x_test, y_test, y_test_labels = dataset.load_test_data()


    # if smaller_data:
    #     x_train, y_train, y_train_labels = x_train[:smaller_train_size], y_train[:smaller_train_size], y_train_labels[:smaller_train_size]
    #     x_test, y_test, y_test_labels = x_test[:smaller_test_size], y_test[:smaller_test_size], y_test_labels[:smaller_test_size]


    # test_size = y_test.size
    # train_size = y_train.size




    # evaluate_early_stopping(15, 100, 10)

    # train(5, 20)
    # accuracy_5_20 = evaluate(5, 20)

    # train(2, 40)
    # accuracy_5_40 = evaluate(5, 40)

    # train(3, 100)
    # evaluate(4, 80)
    # accuracy_5_40 = evaluate(5, 40)
    # accuracy_3_60 = evaluate(3, 60)
    # accuracy_10_60 = evaluate(10, 60)



    # train_scores, test_scores = transfer_learning.transfer_values_svm_scores(transfer_values_train, y_train, transfer_values_test, y_test)
    # print(svm_res.shape)
    # print(transfer_values_train.shape)

    # svm_train_path = r'/cs/labs/daphna/guy.hacohen/project/data/stl10/svm_train_values.pkl'
    # svm_test_path = r'/cs/labs/daphna/guy.hacohen/project/data/stl10/svm_train_values.pkl'

    # with open(svm_train_path, 'wb') as file_pi:
    #     pickle.dump(train_scores, file_pi)

    # with open(svm_test_path, 'wb') as file_pi:
    #     pickle.dump(test_scores, file_pi)



    # # to ask daphna why the score is so good
    #
    # train_scores, test_scores = transfer_learning.get_svm_scores(transfer_values_train, y_train,
    #                                                              transfer_values_test, y_test, dataset)
    # print(np.argmax(train_scores, axis=1))
    # print(y_train)
    #
    # print(np.mean(np.argmax(train_scores, axis=1) == y_train))
    #
    # print(np.mean(np.argmax(test_scores, axis=1) == y_test))
    #
    #
    # print(test_scores.shape)
    # print(train_scores.shape)

    # order = transfer_learning.rank_data_according_to_score(train_scores, y_train)
    #
    # svm_scheduler = creatue_svm_data_scheduler()
    #
    # train_with_stops_2(2, 3, 2, early_stop_name_with_stops_curriculum, svm_scheduler)
    # image_utils.plot_images(x_train[order[:101], :, :, :], 10)
    # image_utils.plot_images(x_train[order[-101:], :, :, :], 10)

    # check_on_real_data('/cs/labs/daphna/guy.hacohen/project/models/vanilla')

    #
    # check_on_real_data('models/debug_cifar_100')
    # history = curriculum_model('debug_cifar100_curriculum', anti_corriculum=True)
    # history = curriculum_model('debug_cifar100_anticurriculum', anti_corriculum=True)
    # history = curriculum_model('debug_cifar100_random', random=True)

    # i = 0
    # cifar100_subset.set_superclass_idx(i)

    #
    # draw_results.plot_cifar_100(dataset.x_train)
    # dataset.set_superclass_idx(16)
    # draw_results.plot_cifar_100(dataset.x_train)
    # dataset.set_superclass_idx(0)
    # draw_results.plot_cifar_100(dataset.x_train)



    # draw_results.plot_keras_history(history)

    # model = load_model('/cs/labs/daphna/guy.hacohen/project/models/debug_cifar100_curriculum')
    # train_keras_model.evaluate_model(model, x_train, y_train_labels, x_test, y_test_labels)


    #
    # train_x, train_y, train_y_lables = dataset.load_training_data()
    # test_x, test_y, test_y_lables = dataset.load_test_data()
    #
    # print(train_x.shape)
    # print(train_y_lables.shape)
    # print(len(train_y))
    # print(test_x.shape)
    # print(test_y_lables.shape)
    # print(len(test_y))
    #
