#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This script contains the celery tasks that will be executed from django views.

@author: George Tzelepis, Ioannis Stenos
"""
from celery.task import task
from create_cluster import YarnCluster
from okeanos_utils import destroy_cluster


@task()
def create_cluster_async(choices):
    """
    Asynchronous create cluster task.
    """
    new_yarn_cluster = YarnCluster(choices)
    MASTER_IP, servers ,password= new_yarn_cluster.create_yarn_cluster()
    task_result = {"master_IP": MASTER_IP, "master_VM_password": password}

    return task_result

@task()
def destroy_cluster_async(token, cluster_id):
    """
    Asynchronous destroy cluster task.
    """
    result = destroy_cluster(token, cluster_id)
    return result

