#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Views for django rest framework .

@author: Ioannis Stenos, Nick Vrionis
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from kamaki.clients import ClientError
from authenticate_user import *
from django.views import generic
from get_flavors_quotas import project_list_flavor_quota
from backend.models import *
from serializers import OkeanosTokenSerializer, UserInfoSerializer, \
    ClusterCreationParamsSerializer, ClusterchoicesSerializer, \
    DeleteClusterSerializer, TaskSerializer, UserThemeSerializer, \
    HdfsSerializer
from django_db_after_login import *
from cluster_errors_constants import *
from tasks import create_cluster_async, destroy_cluster_async, \
    hadoop_cluster_action_async, put_hdfs_async
from create_cluster import YarnCluster
from celery.result import AsyncResult
from reroute_ssh import HdfsRequest


logging.addLevelName(REPORT, "REPORT")
logging.addLevelName(SUMMARY, "SUMMARY")
logger = logging.getLogger("report")

logging_level = REPORT
logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s',
                   level=logging_level, datefmt='%H:%M:%S')

class MainPageView(generic.TemplateView):
    """Load the template file"""
    template_name = 'index.html'

main_page = MainPageView.as_view()


class HdfsView(APIView):
    """
    View for handling requests for file transfer to Hdfs.
    """
    authentication_classes = (EscienceTokenAuthentication, )
    permission_classes = (IsAuthenticated, )
    resource_name = 'hdfs'
    serializer_class = HdfsSerializer

    def post(self, request, *args, **kwargs):
        """
        Put file in Hdfs from Ftp,Http,Https or Pithos.
        """
        serializer = self.serializer_class(data=request.DATA)
        if serializer.is_valid():
            cluster = ClusterInfo.objects.get(id=serializer.data['id'])
            if not serializer.data['user']:
                serializer.data['user'] = ''
            if not serializer.data['password']:
                serializer.data['password'] = ''
            user_args = dict()
            user_args = serializer.data.copy()
            user_args.update({'master_IP': cluster.master_IP})
            hdfs_task = put_hdfs_async.delay(user_args)
            task_id = hdfs_task.id
            return Response({"id":1, "task_id": task_id}, status=status.HTTP_202_ACCEPTED)
        # This will be send if user's cluster parameters are not de-serialized
        # correctly.
        return Response(serializer.errors)


class JobsView(APIView):
    """
    View to get info for celery tasks.
    """
    authentication_classes = (EscienceTokenAuthentication, )
    permission_classes = (IsAuthenticated, )
    resource_name = 'job'
    serializer_class = TaskSerializer

    def get(self, request, *args, **kwargs):
        """
        Get method for celery task state.
        """
        serializer = self.serializer_class(data=request.DATA)
        if serializer.is_valid():
            task_id = serializer.data['task_id']
            c_task = AsyncResult(task_id)
            user_token = Token.objects.get(key=request.auth)
            user = UserInfo.objects.get(user_id=user_token.user.user_id)

            if c_task.ready():
                if c_task.successful():
                    return Response({'success': c_task.result})
                return Response({'error': c_task.result["exc_message"]})

            else:
                return Response({'state': c_task.state})
        return Response(serializer.errors)


class StatusView(APIView):
    """
    View to handle requests for retrieving cluster creation parameters
    from ~okeanos and checking user's choices for cluster creation
    coming from ember.
    """
    authentication_classes = (EscienceTokenAuthentication, )
    permission_classes = (IsAuthenticatedOrIsCreation, )
    resource_name = 'cluster'
    serializer_class = ClusterCreationParamsSerializer

    def get(self, request, *args, **kwargs):
        """
        Return a serialized ClusterCreationParams model with information
        retrieved by kamaki calls. User with corresponding status will be
        found by the escience token.
        """
        user_token = Token.objects.get(key=request.auth)
        self.user = UserInfo.objects.get(user_id=user_token.user.user_id)
        retrieved_cluster_info = project_list_flavor_quota(self.user)
        serializer = self.serializer_class(retrieved_cluster_info, many=True)
        return Response(serializer.data)


    def put(self, request, *args, **kwargs):
        """
        Handles ember requests with user's cluster creation parameters.
        Check the parameters with HadoopCluster object from create_cluster
        script.
        """
        self.resource_name = 'clusterchoice'
        self.serializer_class = ClusterchoicesSerializer
        serializer = self.serializer_class(data=request.DATA)
        if serializer.is_valid():
            user_token = Token.objects.get(key=request.auth)
            user = UserInfo.objects.get(user_id=user_token.user.user_id)
            if serializer.data['hadoop_status']:
                try:
                    cluster_action = hadoop_cluster_action_async.delay(serializer.data['id'],
                                                                       serializer.data['hadoop_status'])
                    task_id = cluster_action.id
                    return Response({"id":1, "task_id": task_id}, status=status.HTTP_202_ACCEPTED)
                except Exception, e:
                    return Response({"status": str(e.args[0])})

            # Dictionary of YarnCluster arguments
            choices = dict()
            choices = serializer.data.copy()
            choices.update({'token': user.okeanos_token})
            try:
                YarnCluster(choices).check_user_resources()
            except ClientError, e:
                return Response({"id": 1, "message": e.message})
            except Exception, e:
                return Response({"id": 1, "message": e.args[0]})
            c_cluster = create_cluster_async.delay(choices)
            task_id = c_cluster.id
            return Response({"id":1, "task_id": task_id}, status=status.HTTP_202_ACCEPTED)

        # This will be send if user's cluster parameters are not de-serialized
        # correctly.
        return Response(serializer.errors)


    def delete(self, request, *args, **kwargs):
        """
        Delete cluster from ~okeanos.
        """
        self.resource_name = 'clusterchoice'
        self.serializer_class = DeleteClusterSerializer
        serializer = self.serializer_class(data=request.DATA)
        if serializer.is_valid():
            user_token = Token.objects.get(key=request.auth)
            user = UserInfo.objects.get(user_id=user_token.user.user_id)
            d_cluster = destroy_cluster_async.delay(user.okeanos_token, serializer.data['id'])
            task_id = d_cluster.id
            return Response({"id":1, "task_id": task_id}, status=status.HTTP_202_ACCEPTED)
        # This will be send if user's delete cluster parameters are not de-serialized
        # correctly.
        return Response(serializer.errors)


class SessionView(APIView):
    """
    View to handle requests from ember for user login and logout and
    user theme update
    """
    authentication_classes = (EscienceTokenAuthentication, )
    permission_classes = (IsAuthenticatedOrIsCreation, )
    resource_name = 'user'
    serializer_class = OkeanosTokenSerializer
    user = None

    def get(self, request, *args, **kwargs):
        """
        Return a UserInfo object from db.
        User will be found by the escience token.
        """
        user_token = Token.objects.get(key=request.auth)
        self.user = UserInfo.objects.get(user_id=user_token.user.user_id)
        self.serializer_class = UserInfoSerializer(self.user)
        return Response(self.serializer_class.data)

    def post(self, request, *args, **kwargs):
        """
        Authenticate a user with a ~okeanos token.  Return
        appropriate success flag, user id, cluster number
        and escience token or appropriate  error messages in case of
        error.
        """
        serializer = self.serializer_class(data=request.DATA)
        if serializer.is_valid():
            token = serializer.data['token']
            if check_user_credentials(token) == AUTHENTICATED:
                self.user = db_after_login(token)
                self.serializer_class = UserInfoSerializer(self.user)
                return Response(self.serializer_class.data)
            else:
                return Response(status=status.HTTP_401_UNAUTHORIZED)
        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, *args, **kwargs):
        """
        Updates user status in database on user logout or user theme change.
        """
        user_token = Token.objects.get(key=request.auth)
        self.user = UserInfo.objects.get(user_id=user_token.user.user_id)
        self.serializer_class = UserThemeSerializer
        serializer = self.serializer_class(data=request.DATA)
        if serializer.is_valid():
            if serializer.data['user_theme']:
                self.user.user_theme = serializer.data['user_theme']
                self.user.save()
            else:
                db_logout_entry(self.user)

            self.serializer_class = UserInfoSerializer(self.user)
            return Response(self.serializer_class.data)

        else:
            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)