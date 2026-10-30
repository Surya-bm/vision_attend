from django.contrib import admin
from .models import Person, VwPersonInfo, Section, Camera, PersonFace

# ---------------- Person Admin ----------------
@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "face_embedding")
    search_fields = ("id", "name")
    list_per_page = 25

# ---------------- VwPersonInfo Admin ----------------
@admin.register(VwPersonInfo)
class VwPersonInfoAdmin(admin.ModelAdmin):
    list_display = ("id", "employee_no", "name", "designation_name", "department_name")
    search_fields = ("employee_no", "name")
    list_per_page = 25

# ---------------- Section Admin ----------------
# @admin.register(Section)
admin.site.register(Section)
# class SectionAdmin(admin.ModelAdmin):
#     list_display = ("id", "status", "created_by", "created_at", "updated_at", "display_order", "name")
#     search_fields = ("name", "created_by")
#     list_filter = ("status",)
#     ordering = ("display_order", "name")
#     readonly_fields = ("created_at", "updated_at")
#     list_per_page = 25


# ---------------- CameraConfiguration Admin ----------------
@admin.register(Camera)
class CameraConfigurationAdmin(admin.ModelAdmin):

    list_display = (
        "unique_id",
        "asset_no",
        "type",
        "serial_number",
        "model_name",
        "ip_address",
        "port",
        "instance_url",
        "stream_url",
        "is_working",
        "display_order",
    )

    search_fields = (
        "asset_no",
        "serial_number",
        "model_name",
        "ip_address",
        "instance_url",
        "stream_url",
    )

    list_filter = (
        "status",
        "is_working",
    )

    ordering = (
        "display_order",
        "unique_id",
    )

    readonly_fields = (
        "created_on",
        "updated_on",
    )

    list_per_page = 25

# ---------------- PersonFace Admin ----------------
# @admin.register(PersonFace)
admin.site.register(PersonFace)
# class PersonFaceAdmin(admin.ModelAdmin):
#     list_display = ("id", "status", "unique_id", "time_in","time_out")
#     search_fields = ("unique_id", "time_in","time_out")
#     list_filter = ("time_in","time_out",)
#     readonly_fields = ("created_on",)
#     list_per_page = 25
