// -----------------------------------------------------------------------------
// Core Domain Models for Madrasati Flutter App
// -----------------------------------------------------------------------------

class UserAccount {
  final String id;
  final String phone;
  final String fullName;
  final String email;
  final bool isPlatformAdmin;
  final bool phoneVerified;

  UserAccount({
    required this.id,
    required this.phone,
    required this.fullName,
    required this.email,
    required this.isPlatformAdmin,
    required this.phoneVerified,
  });

  factory UserAccount.fromJson(Map<String, dynamic> json) {
    return UserAccount(
      id: json['id']?.toString() ?? '',
      phone: json['phone']?.toString() ?? '',
      fullName: json['full_name']?.toString() ?? json['name']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      isPlatformAdmin: json['is_platform_admin'] == true,
      phoneVerified: json['phone_verified'] == true,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'phone': phone,
    'full_name': fullName,
    'email': email,
    'is_platform_admin': isPlatformAdmin,
    'phone_verified': phoneVerified,
  };
}

class SchoolContextItem {
  final String schoolId;
  final String schoolCode;
  final String schoolName;
  final List<String> roles;
  final bool isDefault;

  SchoolContextItem({
    required this.schoolId,
    required this.schoolCode,
    required this.schoolName,
    required this.roles,
    required this.isDefault,
  });

  factory SchoolContextItem.fromJson(Map<String, dynamic> json) {
    final rawRoles = json['roles'];
    List<String> parsedRoles = [];
    if (rawRoles is List) {
      parsedRoles = rawRoles.map((r) => r.toString()).toList();
    }
    return SchoolContextItem(
      schoolId: json['school_id']?.toString() ?? '',
      schoolCode: json['school_code']?.toString() ?? '',
      schoolName: json['school_name']?.toString() ?? 'المدرسة الافتراضية',
      roles: parsedRoles,
      isDefault: json['is_default'] == true,
    );
  }

  Map<String, dynamic> toJson() => {
    'school_id': schoolId,
    'school_code': schoolCode,
    'school_name': schoolName,
    'roles': roles,
    'is_default': isDefault,
  };
}

class MyProfilesResponse {
  final List<TeacherProfileItem> teachers;
  final List<GuardianProfileItem> guardians;
  final List<StudentProfileItem> students;
  final List<StaffProfileItem> staff;

  MyProfilesResponse({
    required this.teachers,
    required this.guardians,
    required this.students,
    required this.staff,
  });

  factory MyProfilesResponse.fromJson(Map<String, dynamic> json) {
    return MyProfilesResponse(
      teachers: (json['teachers'] as List? ?? [])
          .map((i) => TeacherProfileItem.fromJson(i))
          .toList(),
      guardians: (json['guardians'] as List? ?? [])
          .map((i) => GuardianProfileItem.fromJson(i))
          .toList(),
      students: (json['students'] as List? ?? [])
          .map((i) => StudentProfileItem.fromJson(i))
          .toList(),
      staff: (json['staff'] as List? ?? [])
          .map((i) => StaffProfileItem.fromJson(i))
          .toList(),
    );
  }
}

class TeacherProfileItem {
  final String id;
  final String employeeNumber;
  final String specialization;

  TeacherProfileItem({
    required this.id,
    required this.employeeNumber,
    required this.specialization,
  });

  factory TeacherProfileItem.fromJson(Map<String, dynamic> json) {
    return TeacherProfileItem(
      id: json['id']?.toString() ?? '',
      employeeNumber: json['employee_number']?.toString() ?? '',
      specialization: json['specialization']?.toString() ?? '',
    );
  }
}

class GuardianProfileItem {
  final String id;
  final String relationshipType;
  final int childrenCount;

  GuardianProfileItem({
    required this.id,
    required this.relationshipType,
    required this.childrenCount,
  });

  factory GuardianProfileItem.fromJson(Map<String, dynamic> json) {
    return GuardianProfileItem(
      id: json['id']?.toString() ?? '',
      relationshipType: json['relationship_type']?.toString() ?? 'father',
      childrenCount: (json['children_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class StudentProfileItem {
  final String id;
  final String studentIdNumber;
  final String fullName;
  final String sectionId;

  StudentProfileItem({
    required this.id,
    required this.studentIdNumber,
    required this.fullName,
    required this.sectionId,
  });

  factory StudentProfileItem.fromJson(Map<String, dynamic> json) {
    return StudentProfileItem(
      id: json['id']?.toString() ?? '',
      studentIdNumber: json['student_id_number']?.toString() ?? '',
      fullName: json['full_name']?.toString() ?? '',
      sectionId: json['section_id']?.toString() ?? '',
    );
  }
}

class StaffProfileItem {
  final String id;
  final String employeeNumber;
  final String jobTitle;
  final String role;

  StaffProfileItem({
    required this.id,
    required this.employeeNumber,
    required this.jobTitle,
    required this.role,
  });

  factory StaffProfileItem.fromJson(Map<String, dynamic> json) {
    return StaffProfileItem(
      id: json['id']?.toString() ?? '',
      employeeNumber: json['employee_number']?.toString() ?? '',
      jobTitle: json['job_title']?.toString() ?? '',
      role: json['role']?.toString() ?? '',
    );
  }
}

class StudentProfile {
  final String id;
  final String studentNumber;
  final String fullName;
  final String stage;
  final String grade;
  final String section;
  final String avatarUrl;
  final double attendanceRate;
  final double gpa;
  final String schoolName;
  final String schoolCode;

  StudentProfile({
    required this.id,
    required this.studentNumber,
    required this.fullName,
    required this.stage,
    required this.grade,
    required this.section,
    required this.avatarUrl,
    required this.attendanceRate,
    required this.gpa,
    required this.schoolName,
    required this.schoolCode,
  });

  factory StudentProfile.fromJson(Map<String, dynamic> json, {String schoolName = 'المدرسة الافتراضية', String schoolCode = '1234'}) {
    return StudentProfile(
      id: json['id']?.toString() ?? '',
      studentNumber: json['student_id_number']?.toString() ?? json['student_number']?.toString() ?? '',
      fullName: json['name']?.toString() ?? json['full_name']?.toString() ?? 'طالب',
      stage: json['stage']?.toString() ?? (json['grade']?.toString().contains('ثانوي') == true ? 'المرحلة الثانوية' : 'التعليم الأساسي'),
      grade: json['grade']?.toString() ?? 'الصف الأول الثانوي',
      section: json['section']?.toString() ?? 'الشعبة (أ)',
      avatarUrl: json['avatar_url']?.toString() ?? 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&q=80&w=200',
      attendanceRate: (json['attendance_rate'] as num?)?.toDouble() ?? 98.0,
      gpa: (json['gpa'] as num?)?.toDouble() ?? 94.8,
      schoolName: json['school_name']?.toString() ?? schoolName,
      schoolCode: json['school_code']?.toString() ?? schoolCode,
    );
  }
}

class DeviceRecord {
  final String id;
  final String deviceName;
  final String deviceModel;
  final String ipAddress;
  final String lastActive;
  final bool isCurrentDevice;
  bool isConfirmed;
  final bool isAutoConfirmed;

  DeviceRecord({
    required this.id,
    required this.deviceName,
    required this.deviceModel,
    required this.ipAddress,
    required this.lastActive,
    required this.isCurrentDevice,
    required this.isConfirmed,
    required this.isAutoConfirmed,
  });
}

class HomeworkItem {
  final String id;
  final String title;
  final String subject;
  final String teacherName;
  final String dueDate;
  String status; // 'pending', 'submitted', 'graded'
  final int maxScore;
  int? studentScore;
  final String description;
  final String submissionType; // 'interactive_questions', 'image_upload'
  String? submittedImageUrl;
  String? submittedNotes;
  String? teacherFeedback;
  final List<QuestionItem> questions;

  HomeworkItem({
    required this.id,
    required this.title,
    required this.subject,
    required this.teacherName,
    required this.dueDate,
    required this.status,
    required this.maxScore,
    this.studentScore,
    required this.description,
    this.submissionType = 'interactive_questions',
    this.submittedImageUrl,
    this.submittedNotes,
    this.teacherFeedback,
    required this.questions,
  });
}

class QuestionItem {
  final String id;
  final String text;
  final String type; // 'mcq', 'essay'
  final List<String>? options;
  final int points;
  String? userAnswer;

  QuestionItem({
    required this.id,
    required this.text,
    required this.type,
    this.options,
    required this.points,
    this.userAnswer,
  });
}

class GradeRecord {
  final String subject;
  final String teacher;
  double monthOneExam;
  double monthTwoExam;
  double monthlyExam;
  double homeworkScore;
  double participation;
  double semesterFinalExam;
  double total;
  final double maxTotal;
  String letterGrade;
  final String teacherRemarks;
  final int classRank;

  GradeRecord({
    required this.subject,
    required this.teacher,
    this.monthOneExam = 19.0,
    this.monthTwoExam = 18.5,
    required this.monthlyExam,
    required this.homeworkScore,
    required this.participation,
    this.semesterFinalExam = 48.0,
    required this.total,
    required this.maxTotal,
    required this.letterGrade,
    this.teacherRemarks = 'طالب متميز ومشارك فعال وله فهم فيزيائي ورياضي دقيق.',
    this.classRank = 1,
  });
}

class TeacherStudentGradeRow {
  final String studentId;
  final String studentNumber;
  final String studentName;
  double examScore;
  double homeworkScore;
  double participationScore;
  double get total => examScore + homeworkScore + participationScore;
  String get letterGrade {
    final t = total;
    if (t >= 48) return 'ممتاز مرتفع A+';
    if (t >= 45) return 'ممتاز A';
    if (t >= 40) return 'جيد جداً B+';
    if (t >= 35) return 'جيد B';
    return 'مقبول C';
  }

  TeacherStudentGradeRow({
    required this.studentId,
    required this.studentNumber,
    required this.studentName,
    required this.examScore,
    required this.homeworkScore,
    required this.participationScore,
  });
}

class TeacherHomeworkSubmission {
  final String id;
  final String homeworkId;
  final String studentId;
  final String studentName;
  final String submittedDate;
  final String solutionImageUrl;
  final String? studentNote;
  double? score;
  String? teacherNote;
  bool isGraded;

  TeacherHomeworkSubmission({
    required this.id,
    required this.homeworkId,
    required this.studentId,
    required this.studentName,
    required this.submittedDate,
    required this.solutionImageUrl,
    this.studentNote,
    this.score,
    this.teacherNote,
    this.isGraded = false,
  });
}

class TimetablePeriod {
  final int periodNumber;
  final String time;
  final String subject;
  final String teacher;
  final String classroom;
  final String dayName;

  TimetablePeriod({
    required this.periodNumber,
    required this.time,
    required this.subject,
    required this.teacher,
    required this.classroom,
    required this.dayName,
  });
}

class AttendanceDay {
  final String date;
  final String dayName;
  final String status; // 'present', 'absent', 'excused', 'late'
  final String? note;

  AttendanceDay({
    required this.date,
    required this.dayName,
    required this.status,
    this.note,
  });
}

class InvoiceRecord {
  final String invoiceNumber;
  final String title;
  final double totalAmount;
  final double paidAmount;
  final double remainingAmount;
  final String dueDate;
  final String status;

  InvoiceRecord({
    required this.invoiceNumber,
    required this.title,
    required this.totalAmount,
    required this.paidAmount,
    required this.remainingAmount,
    required this.dueDate,
    required this.status,
  });
}

class ChatMessage {
  final String id;
  final String senderName;
  final String text;
  final String time;
  final bool isMe;
  final String senderRole;

  ChatMessage({
    required this.id,
    required this.senderName,
    required this.text,
    required this.time,
    required this.isMe,
    required this.senderRole,
  });
}

class SubjectCurriculum {
  final String id;
  final String code;
  final String name;
  final String shortName;
  final String teacherName;
  final int weeklyPeriods;
  final double maxScore;
  final String textbookTitle;
  final String textbookPdfUrl;
  final int totalPages;
  final double progressPercent; // 0.0 - 1.0
  final String iconName;
  final List<CurriculumUnit> units;

  SubjectCurriculum({
    required this.id,
    required this.code,
    required this.name,
    required this.shortName,
    required this.teacherName,
    required this.weeklyPeriods,
    required this.maxScore,
    required this.textbookTitle,
    required this.textbookPdfUrl,
    required this.totalPages,
    required this.progressPercent,
    required this.iconName,
    required this.units,
  });
}

class CurriculumUnit {
  final int unitNumber;
  final String title;
  final int lessonsCount;
  final String summary;
  final List<String> keyTopics;
  final bool isCompleted;

  CurriculumUnit({
    required this.unitNumber,
    required this.title,
    required this.lessonsCount,
    required this.summary,
    required this.keyTopics,
    this.isCompleted = false,
  });
}

class TeacherAttendanceStudent {
  final String studentId;
  final String studentName;
  final String studentNumber;
  final String avatarUrl;
  String status; // 'present', 'absent', 'late', 'excused'
  String? note;

  TeacherAttendanceStudent({
    required this.studentId,
    required this.studentName,
    required this.studentNumber,
    required this.avatarUrl,
    this.status = 'present',
    this.note,
  });
}

class DailyLessonPlan {
  final String id;
  final String date;
  final String subject;
  final String className;
  final String period;
  final String topic;
  final String objectives;
  final String pages;
  final String teachingAids;
  final String homeworkAssigned;
  final String notes;
  bool isCompleted;

  DailyLessonPlan({
    required this.id,
    required this.date,
    required this.subject,
    required this.className,
    required this.period,
    required this.topic,
    required this.objectives,
    required this.pages,
    required this.teachingAids,
    required this.homeworkAssigned,
    required this.notes,
    this.isCompleted = true,
  });
}

class AbsenceExcuse {
  final String id;
  final String studentId;
  final String studentName;
  final String date;
  final String reason;
  final String? medicalReportUrl;
  final String status; // 'pending', 'approved', 'rejected'
  final String submittedAt;

  AbsenceExcuse({
    required this.id,
    required this.studentId,
    required this.studentName,
    required this.date,
    required this.reason,
    this.medicalReportUrl,
    this.status = 'pending',
    required this.submittedAt,
  });
}
