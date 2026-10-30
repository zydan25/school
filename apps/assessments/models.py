"""Assessment, gradebook, and exam control domain models."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TenantOwnedModel


class AssessmentType(TenantOwnedModel):
    """أنواع التقييمات والاختبارات المعتمدة في المدرسة."""
    name = models.CharField("نوع التقييم", max_length=100)
    code = models.CharField("رمز التقييم", max_length=50)
    default_max_score = models.DecimalField("الدرجة العظمى الافتراضية", max_digits=6, decimal_places=2, default=100.00)
    weight_percentage = models.DecimalField("الوزن النسبي (%)", max_digits=5, decimal_places=2, default=20.00)

    class Meta:
        verbose_name = "نوع تقييم"
        verbose_name_plural = "أنواع التقييمات"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "code"],
                condition=models.Q(is_archived=False),
                name="assessments_type_school_code_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.weight_percentage}%)"


class GradeBook(TenantOwnedModel):
    """سجل رصد الدرجات والتقييمات للطلاب."""
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.PROTECT,
        related_name="grade_records",
    )
    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة الدراسية",
        on_delete=models.PROTECT,
        related_name="grade_records",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        verbose_name="الفصل الدراسي",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="grade_records",
    )
    assessment_type = models.ForeignKey(
        AssessmentType,
        verbose_name="نوع التقييم",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="grades",
    )
    homework = models.ForeignKey(
        "assignments.Homework",
        verbose_name="الواجب المرتبط (إن وجد)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="gradebook_entries",
    )
    assessment_title = models.CharField("عنوان التقييم / الاختبار", max_length=255)
    score = models.DecimalField("الدرجة المحصلة", max_digits=6, decimal_places=2)
    max_score = models.DecimalField("الدرجة العظمى", max_digits=6, decimal_places=2, default=100.00)
    teacher_feedback = models.TextField("ملاحظات المعلم / تقرير الذكاء الاصطناعي", blank=True)
    graded_by = models.ForeignKey(
        "staff.Teacher",
        verbose_name="المعلم الراصد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="graded_records",
    )
    graded_at = models.DateTimeField("تاريخ الرصد والتقييم", default=timezone.now)
    is_published = models.BooleanField("منشورة للطالب وولي الأمر", default=True)

    class Meta:
        verbose_name = "سجل درجات"
        verbose_name_plural = "دفتر الدرجات والنتائج"
        indexes = [
            models.Index(fields=["school", "student", "subject"]),
            models.Index(fields=["school", "student", "is_published"]),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.assessment_title}: {self.score}/{self.max_score}"

    def clean(self):
        super().clean()
        if self.score is not None and self.max_score is not None and self.score > self.max_score:
            raise ValidationError({"score": "الدرجة المحصلة لا يمكن أن تتجاوز الدرجة العظمى."})
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})
        if self.subject_id and self.subject.school_id != self.school_id:
            raise ValidationError({"subject": "المادة لا تتبع نفس المدرسة."})
        if self.graded_by_id and self.graded_by.school_id != self.school_id:
            raise ValidationError({"graded_by": "المعلم لا يتبع نفس المدرسة."})


# -----------------------------------------------------------------------------
# Exam Control Room, Seating, and Committees (كنترول الاختبارات ولجان الامتحانات)
# -----------------------------------------------------------------------------

class ExamCommittee(TenantOwnedModel):
    """لجان سير الامتحانات وقاعات الكنترول."""
    name = models.CharField("اسم اللجنة / القاعة", max_length=150)
    committee_number = models.CharField("رقم اللجنة", max_length=50)
    location_room = models.CharField("موقع اللجنة / القاعة", max_length=150)
    capacity = models.PositiveSmallIntegerField("السعة القصوى للجنة", default=25)
    head_supervisor = models.ForeignKey(
        "staff.Teacher",
        verbose_name="رئيس اللجنة والمراقب الأول",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_committees",
    )

    class Meta:
        verbose_name = "لجنة اختبارات (كنترول)"
        verbose_name_plural = "لجان الامتحانات والكنترول"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "committee_number"],
                condition=models.Q(is_archived=False),
                name="assessments_committee_num_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"لجنة #{self.committee_number} - {self.name} ({self.location_room})"


class ExamSeating(TenantOwnedModel):
    """أرقام الجلوس والأرقام السرية للطلاب في الكنترول."""
    academic_year = models.ForeignKey(
        "academics.AcademicYear",
        verbose_name="العام الدراسي",
        on_delete=models.PROTECT,
        related_name="exam_seatings",
    )
    committee = models.ForeignKey(
        ExamCommittee,
        verbose_name="لجنة الاختبار",
        on_delete=models.PROTECT,
        related_name="seatings",
    )
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="exam_seatings",
    )
    seating_number = models.PositiveIntegerField("رقم الجلوس المعلن")
    secret_code = models.CharField("الرقم السري للكنترول (للتصحيح المعمى)", max_length=50, blank=True)

    class Meta:
        verbose_name = "رقم جلوس طالب"
        verbose_name_plural = "أرقام الجلوس والكنترول"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "academic_year", "seating_number"],
                condition=models.Q(is_archived=False),
                name="assessments_seating_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["school", "academic_year", "student"],
                condition=models.Q(is_archived=False),
                name="assessments_student_year_seating_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"رقم جلوس ({self.seating_number}) - {self.student} [لجنة: {self.committee.name}]"

    def clean(self):
        super().clean()
        if self.school_id and self.academic_year_id and self.academic_year.school_id != self.school_id:
            raise ValidationError({"academic_year": "العام الدراسي لا يتبع نفس المدرسة."})
        if self.committee_id and self.committee.school_id != self.school_id:
            raise ValidationError({"committee": "اللجنة لا تتبع نفس المدرسة."})
        if self.student_id and self.student.school_id != self.school_id:
            raise ValidationError({"student": "الطالب لا يتبع نفس المدرسة."})
        if self.committee_id and self.academic_year_id:
            count = ExamSeating.objects.filter(
                school=self.school,
                committee=self.committee,
                academic_year=self.academic_year,
                is_archived=False,
            ).exclude(pk=self.pk).count()
            if count >= self.committee.capacity:
                raise ValidationError({"committee": f"تجاوزت اللجنة سعتها الاستيعابية القصوى ({self.committee.capacity} طالب)."})


# -----------------------------------------------------------------------------
# Question Bank, Online Remote Exams, and Automated Grading
# -----------------------------------------------------------------------------

class QuestionBank(TenantOwnedModel):
    """بنك الأسئلة للمواد والوحدات الدراسية مع نماذج الإجابات وأنواعها."""
    class QuestionType(models.TextChoices):
        MCQ = "mcq", "اختيار من متعدد"
        TRUE_FALSE = "true_false", "صح أو خطأ"
        SHORT_ANSWER = "short_answer", "إجابة قصيرة"
        ESSAY = "essay", "سؤال مقالي تحليلي"

    class Difficulty(models.TextChoices):
        EASY = "easy", "سهل"
        MEDIUM = "medium", "متوسط"
        HARD = "hard", "صعب (تفكير عليا)"

    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة الدراسية",
        on_delete=models.CASCADE,
        related_name="questions",
    )
    grade_level = models.ForeignKey(
        "academics.GradeLevel",
        verbose_name="الصف الدراسي",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="questions",
    )
    unit_name = models.CharField("اسم الوحدة / الباب الدراسي (مثال: الوحدة الأولى: التفاضل)", max_length=200)
    topic = models.CharField("عنوان الدرس / الموضوع", max_length=200, blank=True)
    question_text = models.TextField("نص السؤال")
    question_type = models.CharField("نوع السؤال", max_length=20, choices=QuestionType.choices, default=QuestionType.MCQ)
    difficulty = models.CharField("مستوى الصعوبة", max_length=20, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    default_marks = models.DecimalField("الدرجة الافتراضية للسؤال", max_digits=5, decimal_places=2, default=Decimal("1.00"))
    
    # Options for MCQ e.g. [{"id": "A", "text": "خيار 1"}, {"id": "B", "text": "خيار 2"}]
    options_json = models.JSONField("خيارات الإجابة (للاختيار من متعدد)", default=list, blank=True)
    correct_answer = models.CharField("الإجابة الصحيحة أو رمز الخيار الصحيح (مثل A أو صح)", max_length=255)
    model_answer_explanation = models.TextField("شرح الإجابة والحل النموذجي", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المعلم واضع السؤال",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="authored_questions",
    )

    class Meta:
        verbose_name = "سؤال في بنك الأسئلة"
        verbose_name_plural = "بنك الأسئلة المدرسية"
        indexes = [
            models.Index(fields=["school", "subject", "unit_name"]),
        ]

    def __str__(self) -> str:
        return f"[{self.subject.name} - {self.unit_name}] {self.question_text[:50]}... ({self.get_question_type_display()})"


class OnlineExam(TenantOwnedModel):
    """قوالب الاختبارات الشهرية والنصفيّة وإجراء الامتحانات عن بعد."""
    class ExamType(models.TextChoices):
        QUIZ = "quiz", "اختبار قصير (كويز)"
        MONTHLY = "monthly", "اختبار شهري"
        MIDTERM = "midterm", "اختبار نصف الفصل"
        FINAL = "final", "اختبار نهائي"

    title = models.CharField("عنوان الاختبار", max_length=255)
    subject = models.ForeignKey(
        "academics.Subject",
        verbose_name="المادة الدراسية",
        on_delete=models.PROTECT,
        related_name="online_exams",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm",
        verbose_name="الفصل الدراسي",
        on_delete=models.PROTECT,
        related_name="online_exams",
    )
    grade_level = models.ForeignKey(
        "academics.GradeLevel",
        verbose_name="الصف الدراسي المستهدف",
        on_delete=models.PROTECT,
        related_name="online_exams",
    )
    section = models.ForeignKey(
        "academics.Section",
        verbose_name="الشعبة الصفية (اتركه فارغاً لكل شعب الصف)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="online_exams",
    )
    exam_type = models.CharField("نوع الاختبار", max_length=20, choices=ExamType.choices, default=ExamType.MONTHLY)
    duration_minutes = models.PositiveSmallIntegerField("مدة الاختبار (بالدقائق)", default=45)
    total_marks = models.DecimalField("الدرجة العظمى للاختبار", max_digits=6, decimal_places=2, default=Decimal("20.00"))
    passing_marks = models.DecimalField("درجة النجاح الدنيا", max_digits=6, decimal_places=2, default=Decimal("10.00"))
    start_time = models.DateTimeField("تاريخ ووقت بدء الاختبار")
    end_time = models.DateTimeField("تاريخ ووقت إغلاق الاختبار")
    is_published = models.BooleanField("منشور ومتاح للطلاب في موعده", default=True)
    instructions = models.TextField("تعليمات وتوجيهات الاختبار", blank=True)
    questions = models.ManyToManyField(
        QuestionBank,
        verbose_name="الأسئلة المدرجة في الاختبار",
        blank=True,
        related_name="included_in_exams",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المعلم / الكنترول المنشئ",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_online_exams",
    )

    class Meta:
        verbose_name = "قالب اختبار / امتحان إلكتروني"
        verbose_name_plural = "الاختبارات الإلكترونية والامتحانات عن بعد"
        ordering = ["-start_time"]

    def __str__(self) -> str:
        return f"{self.title} - {self.subject.name} ({self.get_exam_type_display()})"


class StudentOnlineExamSubmission(TenantOwnedModel):
    """إجابات ونتائج الطالب في الاختبار الإلكتروني مع التصحيح الآلي."""
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "جارٍ أداء الاختبار"
        SUBMITTED = "submitted", "تم التسليم"
        GRADED = "graded", "تم التصحيح والاعتماد"

    exam = models.ForeignKey(
        OnlineExam,
        verbose_name="الاختبار",
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        "students.Student",
        verbose_name="الطالب",
        on_delete=models.CASCADE,
        related_name="exam_submissions",
    )
    started_at = models.DateTimeField("وقت بدء الحل", default=timezone.now)
    submitted_at = models.DateTimeField("وقت تسليم الإجابات", null=True, blank=True)
    answers_json = models.JSONField("إجابات الطالب المسجلة", default=dict, blank=True)
    auto_score = models.DecimalField("الدرجة المحتسبة آلياً (للموضوعي)", max_digits=6, decimal_places=2, default=Decimal("0.00"))
    manual_score = models.DecimalField("الدرجة المقالية (المضافة من المعلم)", max_digits=6, decimal_places=2, default=Decimal("0.00"))
    final_score = models.DecimalField("الدرجة النهائية المحرزة", max_digits=6, decimal_places=2, default=Decimal("0.00"))
    teacher_feedback = models.TextField("ملاحظات المعلم المصحح", blank=True)
    status = models.CharField("حالة الإجابة", max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="المعلم المصحح والمعتمد",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="graded_exam_submissions",
    )

    class Meta:
        verbose_name = "إجابة اختبار إلكتروني لطالب"
        verbose_name_plural = "سجل إجابات وتصحيح الاختبارات الإلكترونية"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "exam", "student"],
                condition=models.Q(is_archived=False),
                name="assessments_student_exam_uniq",
            )
        ]

    def __str__(self) -> str:
        return f"{self.student}: {self.exam.title} - {self.final_score}/{self.exam.total_marks}"

    def auto_grade(self):
        """تصحيح الأسئلة الموضوعية (اختيار من متعدد وصح وخطأ) آلياً وفورياً."""
        score = Decimal("0.00")
        for q in self.exam.questions.all():
            q_id = str(q.id)
            student_ans = str(self.answers_json.get(q_id, "")).strip().lower()
            correct_ans = str(q.correct_answer).strip().lower()
            if student_ans and student_ans == correct_ans:
                score += q.default_marks

        self.auto_score = score
        self.final_score = self.auto_score + self.manual_score
        self.status = self.Status.GRADED
