from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
import time

# Create your views here.

# --- 1. 用户信息接口 (解决当前的 404 报错) ---
@api_view(['GET'])
@permission_classes([AllowAny]) # 允许未登录访问，方便调试
def user_info(request):
    return Response({
        "code": 0,
        "result": {
            "userId": "1",
            "username": "admin",
            "realName": "系统管理员",
            "avatar": "",
            "desc": "Super Admin",
            # 'super' 是 Vben 默认的超管角色，拥有所有权限
            "roles": ["super"], 
            "token": "fake-token-123",
        },
        "message": "ok",
        "type": "success"
    })

# --- 2. 登录接口 (前端点击登录时需要) ---
@api_view(['POST'])
@permission_classes([AllowAny])
def auth_login(request):
    return Response({
        "code": 0,
        "result": {
            "token": "fake-jwt-token-example",
            "userId": 1
        },
        "message": "登录成功",
        "type": "success"
    })

# --- 3. 菜单接口 (登录后加载左侧菜单需要) ---
@api_view(['GET'])
@permission_classes([AllowAny])
def menu_all(request):
    return Response({
        "code": 0,
        "result": [
            # 这里返回空数组，Vben 会使用前端路由表作为菜单
            # 如果需要后端动态控制菜单，可以在这里返回具体结构
        ],
        "message": "ok",
        "type": "success"
    })
