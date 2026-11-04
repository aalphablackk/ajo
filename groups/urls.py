from django.urls import path
from . import views

app_name = "groups"

urlpatterns = [
    path("create/", views.create_group, name="create_group"),
    path("my-groups/", views.my_groups, name="my_groups"),
    path("<int:group_id>/edit/",views.edit_group,name="edit_group"),
    path("invite/<uuid:token>/",views.invitation_detail,name="invitation_detail"),
    path("<int:group_id>/toggle-invitation/",views.toggle_invitation,name="toggle_invitation"),
    path("<int:group_id>/publish/",views.publish_group,name="publish_group"),
    path("<int:group_id>/close/",views.close_group,name="close_group"),
    path("<int:group_id>/reopen/",views.reopen_group,name="reopen_group"),
    path("<int:group_id>/delete/",views.delete_group,name="delete_group"),
    path("invite/<uuid:token>/request/",views.request_to_join,name="request_to_join"),
    path("<int:group_id>/members/",views.manage_members,name="manage_members"),
    path("<int:group_id>/members/<int:membership_id>/approve/",views.approve_member,name="approve_member"),
    path("<int:group_id>/members/<int:membership_id>/reject/",views.reject_member,name="reject_member"),
    path("<int:group_id>/members/<int:membership_id>/remove/",views.remove_member,name="remove_member"),
    path("<int:group_id>/members/<int:membership_id>/readd/",views.readd_member,name="readd_member"),
]