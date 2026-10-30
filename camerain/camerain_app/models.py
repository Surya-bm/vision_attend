import pickle
from django.db import models


class Users(models.Model):
    name = models.CharField(max_length=200)
    email = models.CharField(max_length=200, unique=True)
    password = models.CharField(max_length=255)  # bcrypt hash

    def __str__(self):
        return self.email

    class Meta:
        managed = False
        db_table = 'users'


class Person(models.Model):
    unique_id = models.BigAutoField(primary_key=True)
    id = models.CharField(max_length=36)
    status = models.BooleanField(default=True)
    created_by_id = models.CharField(max_length=36)
    created_on = models.DateTimeField(null=True, blank=True)
    updated_by_id = models.CharField(max_length=255, null=True, blank=True)
    updated_on = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=255)
    register_number = models.CharField(max_length=255, null=True, blank=True)
    category_id = models.CharField(max_length=36, null=True, blank=True)
    face_embedding = models.BinaryField(null=True, blank=True)
    face_embedding_mask = models.BinaryField(null=True, blank=True)
    image = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=False)  # maps to tinyint(1)

    def set_embedding(self, emb):
        self.face_embedding = pickle.dumps(emb)

    def get_embedding(self):
        if self.face_embedding:
            return pickle.loads(self.face_embedding)

    def set_embedding_mask(self, emb):
        self.face_embedding_mask = pickle.dumps(emb)

    def get_embedding_mask(self):
        if self.face_embedding_mask:
            return pickle.loads(self.face_embedding_mask)

    class Meta:
        managed = False
        db_table = 'person'


class VwPersonInfo(models.Model):
    """Read-only DB view joining person + employee details."""
    id = models.BigIntegerField(primary_key=True)
    employee_no = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255)
    # register_number = models.CharField(max_length=255, null=True, blank=True)
    designation_name = models.CharField(max_length=255)
    department_name = models.CharField(max_length=255)
    employee_photo = models.TextField(null=True, blank=True)
    face_embedding = models.BinaryField(null=True, blank=True)
    face_embedding_mask = models.BinaryField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'vw_person_info'

    def __str__(self):
        return f"{self.employee_no} - {self.name}"


class Section(models.Model):
    unique_id = models.BigAutoField(primary_key=True)
    id = models.CharField(max_length=36)
    status = models.BooleanField(default=True)
    created_by_id = models.CharField(max_length=36)
    created_on = models.DateTimeField()
    updated_by_id = models.CharField(max_length=255, null=True, blank=True)
    updated_on = models.DateTimeField(null=True, blank=True)
    floor_id = models.CharField(max_length=36, null=True, blank=True)
    name = models.CharField(max_length=255)
    register_number = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    display_order = models.BigIntegerField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "section"

    def __str__(self):
        return self.name


class Camera(models.Model):
    unique_id = models.BigAutoField(primary_key=True)
    id = models.CharField(max_length=36)
    status = models.BooleanField(default=True)
    created_by_id = models.CharField(max_length=36)
    created_on = models.DateTimeField()
    updated_by_id = models.CharField(max_length=255, null=True, blank=True)
    updated_on = models.DateTimeField(null=True, blank=True)
    section_id = models.CharField(max_length=36, null=True, blank=True)
    nvr_id = models.CharField(max_length=36, null=True, blank=True)
    asset_no = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)  # "IN" or "OUT"
    serial_number = models.CharField(max_length=255, null=True, blank=True)
    model_name = models.CharField(max_length=255, null=True, blank=True)
    ip_address = models.CharField(max_length=255, null=True, blank=True)
    port = models.BigIntegerField(default=80)
    manufacturer = models.CharField(max_length=255, null=True, blank=True)
    vendor = models.CharField(max_length=255, null=True, blank=True)
    install_date = models.DateField(null=True, blank=True)
    last_working_on = models.DateTimeField(null=True, blank=True)
    is_working = models.BooleanField(default=False)
    instance_url = models.CharField(max_length=255, null=True, blank=True)
    stream_url = models.CharField(max_length=255, null=True, blank=True)
    roi_x = models.BigIntegerField(null=True, blank=True)
    roi_y = models.BigIntegerField(null=True, blank=True)
    roi_height = models.BigIntegerField(null=True, blank=True)
    roi_width = models.BigIntegerField(null=True, blank=True)
    display_order = models.BigIntegerField(default=0)

    class Meta:
        managed = False
        db_table = "camera"

    def __str__(self):
        return f"{self.asset_no} - {self.ip_address}"


class PersonFace(models.Model):
    """Attendance records — one row per person per day (IN + OUT on same row)."""
    unique_id = models.BigAutoField(primary_key=True)
    id = models.CharField(max_length=36)
    status = models.BooleanField(default=True)
    created_by_id = models.CharField(max_length=36)
    created_on = models.DateTimeField()
    updated_by_id = models.CharField(max_length=255, null=True, blank=True)
    updated_on = models.DateTimeField(null=True, blank=True)
    person_id = models.CharField(max_length=36, null=True, blank=True)
    camera_id = models.CharField(max_length=36, null=True, blank=True)
    camera_unique_id = models.BigIntegerField(null=True, blank=True)
    person_no = models.CharField(max_length=255, null=True, blank=True)
    image = models.TextField(null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)  # "IN" or "OUT"

    class Meta:
        managed = False
        db_table = 'person_face'

    def __str__(self):
        return f"{self.person_no} - {self.date}"
