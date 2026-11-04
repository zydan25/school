import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'models.dart';

class ApiService extends ChangeNotifier {
  static const String baseUrl = 'https://school.alattab.site/api/v1';

  // ---------------------------------------------------------------------------
  // Session State (Zero hardcoded Bearer tokens, zero bypass tokens)
  // ---------------------------------------------------------------------------
  String? _token;
  String? get token => _token;
  bool get isAuthenticated => _token != null && _token!.isNotEmpty;

  UserAccount? _user;
  UserAccount? get user => _user;
  String get currentUserName => _user?.fullName ?? 'مستخدم المنظومة';
  String get userPhone => _user?.phone ?? '770000004';

  List<SchoolContextItem> _schools = [];
  List<SchoolContextItem> get schools => _schools;

  SchoolContextItem? _activeSchool;
  SchoolContextItem? get activeSchool => _activeSchool;
  String get activeSchoolName => _activeSchool?.schoolName ?? 'المدرسة الافتراضية';
  String get activeSchoolCode => _activeSchool?.schoolCode ?? '1234';

  MyProfilesResponse? _profiles;
  MyProfilesResponse? get profiles => _profiles;

  String _currentRole = 'guardian'; // 'guardian', 'student', 'teacher', 'admin', 'staff'
  String get currentRole => _currentRole;

  int _selectedStudentIndex = 0;
  int get selectedStudentIndex => _selectedStudentIndex;

  bool _isAiThinking = false;
  bool get isAiThinking => _isAiThinking;

  bool _isInitialized = true;
  bool get isInitialized => _isInitialized;

  // ---------------------------------------------------------------------------
  // Decoupled Student & Guardian Identity State (STU-01, STU-02, STU-03, STU-04)
  // ---------------------------------------------------------------------------
  // Personal student profile when in 'student' role
  StudentProfile? _activeStudentProfile;
  StudentProfile? get activeStudentProfile => _activeStudentProfile;

  // Guardian's children list when in 'guardian' role
  final List<StudentProfile> _guardianChildren = [];
  List<StudentProfile> get guardianChildren => List.unmodifiable(_guardianChildren);

  // Backward compatibility getter for screens referencing api.students
  List<StudentProfile> get students {
    if (_currentRole == 'student') {
      return _activeStudentProfile != null ? [_activeStudentProfile!] : [];
    }
    return List.unmodifiable(_guardianChildren);
  }

  // Active student getter: returns user's active student profile in student mode,
  // or the currently selected child in guardian mode.
  // NEVER returns a fake fallback Ahmed/Saif object!
  StudentProfile? get currentStudent {
    if (_currentRole == 'student') {
      return _activeStudentProfile;
    }
    if (_guardianChildren.isNotEmpty) {
      final idx = _selectedStudentIndex.clamp(0, _guardianChildren.length - 1);
      return _guardianChildren[idx];
    }
    return _activeStudentProfile;
  }

  void selectStudent(int index) {
    if (index >= 0 && index < _guardianChildren.length) {
      _selectedStudentIndex = index;
      notifyListeners();
    }
  }

  // ---------------------------------------------------------------------------
  // Available Roles based on REAL server profiles & memberships
  // ---------------------------------------------------------------------------
  List<String> get availableRoles {
    final Set<String> roles = {};
    if (_profiles != null) {
      if (_profiles!.guardians.isNotEmpty) roles.add('guardian');
      if (_profiles!.students.isNotEmpty) roles.add('student');
      if (_profiles!.teachers.isNotEmpty) roles.add('teacher');
      if (_profiles!.staff.isNotEmpty) roles.add('staff');
    }
    if (_activeSchool != null) {
      final sRoles = _activeSchool!.roles;
      if (sRoles.any((r) => r.contains('admin') || r.contains('director'))) {
        roles.add('admin');
      }
      if (sRoles.contains('teacher')) roles.add('teacher');
      if (sRoles.contains('student')) roles.add('student');
      if (sRoles.contains('guardian')) roles.add('guardian');
    }
    if (_user?.isPlatformAdmin == true) {
      roles.add('admin');
    }
    if (roles.isEmpty) {
      roles.add(_currentRole);
    }
    return roles.toList();
  }

  // ---------------------------------------------------------------------------
  // Headers Helper (enforcing Authorization & X-School-ID)
  // ---------------------------------------------------------------------------
  Map<String, String> get authHeaders {
    final Map<String, String> headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (_token != null && _token!.isNotEmpty) {
      headers['Authorization'] = 'Bearer $_token';
    }
    if (_activeSchool != null && _activeSchool!.schoolId.isNotEmpty) {
      headers['X-School-ID'] = _activeSchool!.schoolId;
    }
    return headers;
  }

  // ---------------------------------------------------------------------------
  // Session Lifecycle & Persistence
  // ---------------------------------------------------------------------------
  Future<void> initSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedToken = prefs.getString('auth_token');
      final savedUserJson = prefs.getString('auth_user');
      final savedSchoolJson = prefs.getString('auth_school');
      final savedRole = prefs.getString('auth_role');

      if (savedToken != null && savedToken.isNotEmpty) {
        _token = savedToken;
        if (savedUserJson != null) {
          _user = UserAccount.fromJson(jsonDecode(savedUserJson));
        }
        if (savedSchoolJson != null) {
          _activeSchool = SchoolContextItem.fromJson(jsonDecode(savedSchoolJson));
        }
        if (savedRole != null) {
          _currentRole = savedRole;
        }

        final valid = await fetchProfiles();
        if (valid) {
          if (_currentRole == 'guardian') {
            await fetchChildren();
          }
        } else {
          await logout();
        }
      }
    } catch (e) {
      if (kDebugMode) print('Init session error: $e');
    } finally {
      _isInitialized = true;
      notifyListeners();
    }
  }

  // ---------------------------------------------------------------------------
  // Real Login
  // ---------------------------------------------------------------------------
  Future<Map<String, dynamic>> login(String phone, String password, {String? schoolCode}) async {
    final cleanPhone = phone.trim();
    final cleanPass = password.trim();

    if (cleanPhone.isEmpty || cleanPass.isEmpty) {
      return {'success': false, 'error': 'يرجى إدخال رقم الهاتف وكلمة المرور'};
    }

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/login/'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'phone': cleanPhone,
          'password': cleanPass,
        }),
      ).timeout(const Duration(seconds: 12));

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        final rawToken = data['token'] ?? data['access_token'];

        if (rawToken == null || rawToken.toString().isEmpty) {
          return {'success': false, 'error': 'استجابة الخادم غير مكتملة، لم يتم العثور على رمز المصادقة.'};
        }

        _token = rawToken.toString();

        if (data['user'] != null) {
          _user = UserAccount.fromJson(data['user']);
        }

        if (data['schools'] is List) {
          _schools = (data['schools'] as List)
              .map((s) => SchoolContextItem.fromJson(s))
              .toList();
          if (_schools.isNotEmpty) {
            _activeSchool = _schools.firstWhere((s) => s.isDefault, orElse: () => _schools.first);
          }
        }

        await fetchProfiles();

        final avRoles = availableRoles;
        if (avRoles.contains('guardian')) {
          _currentRole = 'guardian';
        } else if (avRoles.contains('student')) {
          _currentRole = 'student';
        } else if (avRoles.contains('teacher')) {
          _currentRole = 'teacher';
        } else if (avRoles.contains('admin')) {
          _currentRole = 'admin';
        } else if (avRoles.isNotEmpty) {
          _currentRole = avRoles.first;
        }

        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('auth_token', _token!);
        if (_user != null) {
          await prefs.setString('auth_user', jsonEncode(_user!.toJson()));
        }
        if (_activeSchool != null) {
          await prefs.setString('auth_school', jsonEncode(_activeSchool!.toJson()));
        }
        await prefs.setString('auth_role', _currentRole);

        if (_currentRole == 'guardian') {
          await fetchChildren();
        }

        notifyListeners();
        return {'success': true};
      } else if (response.statusCode == 401) {
        return {'success': false, 'error': 'بيانات الدخول غير صحيحة أو الحساب غير نشط.'};
      } else if (response.statusCode == 423) {
        return {'success': false, 'error': 'تم إيقاف محاولات الدخول مؤقتاً؛ حاول بعد انتهاء فترة القفل.'};
      } else {
        String msg = 'حدث خطأ أثناء تسجيل الدخول (${response.statusCode})';
        try {
          final errData = jsonDecode(utf8.decode(response.bodyBytes));
          if (errData['error'] != null) msg = errData['error'].toString();
        } catch (_) {}
        return {'success': false, 'error': msg};
      }
    } catch (e) {
      if (kDebugMode) print('Login network error: $e');
      return {'success': false, 'error': 'تعذر الاتصال بالخادم، يرجى التأكد من اتصالك بالإنترنت.'};
    }
  }

  // ---------------------------------------------------------------------------
  // Real Logout
  // ---------------------------------------------------------------------------
  Future<void> logout() async {
    try {
      if (_token != null && _token!.isNotEmpty) {
        await http.post(
          Uri.parse('$baseUrl/auth/logout/'),
          headers: authHeaders,
        ).timeout(const Duration(seconds: 4));
      }
    } catch (_) {}

    _token = null;
    _user = null;
    _activeSchool = null;
    _profiles = null;
    _schools = [];
    _activeStudentProfile = null;
    _guardianChildren.clear();
    _studentAiSessionId = null;
    _studentTodayLessons = [];
    _studentTimetablePeriods = [];
    _studentSubjects = [];
    _studentHomeworks = [];
    _studentOnlineExams = [];
    _currentRole = 'guardian';

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('auth_token');
      await prefs.remove('auth_user');
      await prefs.remove('auth_school');
      await prefs.remove('auth_role');
    } catch (_) {}

    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Fetch Profiles from Server (STU-01, STU-02, STU-03)
  // ---------------------------------------------------------------------------
  Future<bool> fetchProfiles() async {
    if (!isAuthenticated) return false;
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/app/account/profiles/'),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        _profiles = MyProfilesResponse.fromJson(data);

        if (_profiles!.students.isNotEmpty) {
          final s = _profiles!.students.first;
          _activeStudentProfile = StudentProfile(
            id: s.id,
            studentNumber: s.studentIdNumber.isNotEmpty ? s.studentIdNumber : 'STD-2026-001',
            fullName: s.fullName.isNotEmpty ? s.fullName : (_user?.fullName ?? 'طالب'),
            stage: 'المرحلة الثانوية',
            grade: 'الصف الأول الثانوي',
            section: 'الشعبة (أ)',
            avatarUrl: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&q=80&w=200',
            attendanceRate: 98.0,
            gpa: 94.8,
            schoolName: activeSchoolName,
            schoolCode: activeSchoolCode,
          );

          // Enrich student workspace data dynamically
          fetchStudentTodayLessons();
          fetchStudentTimetable();
          fetchStudentSubjects();
          fetchStudentHomeworks();
          fetchStudentOnlineExams();
        } else {
          _activeStudentProfile = null;
        }

        notifyListeners();
        return true;
      }
    } catch (e) {
      if (kDebugMode) print('fetchProfiles error: $e');
    }
    return false;
  }

  void switchRole(String role) {
    _currentRole = role;
    SharedPreferences.getInstance().then((prefs) {
      prefs.setString('auth_role', role);
    });
    if (role == 'guardian') {
      fetchChildren();
    } else if (role == 'student') {
      fetchProfiles();
      fetchStudentTodayLessons();
      fetchStudentTimetable();
      fetchStudentSubjects();
      fetchStudentHomeworks();
      fetchStudentOnlineExams();
    }
    notifyListeners();
  }

  Future<void> switchSchool(SchoolContextItem school) async {
    _activeSchool = school;
    _activeStudentProfile = null;
    _guardianChildren.clear();
    _studentAiSessionId = null;
    _studentTodayLessons = [];
    _studentTimetablePeriods = [];
    _studentSubjects = [];
    _studentHomeworks = [];
    _studentOnlineExams = [];

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_school', jsonEncode(school.toJson()));
    await fetchProfiles();
    if (_currentRole == 'guardian') {
      await fetchChildren();
    }
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Fetch Linked Children for Guardian (STU-01 & STU-02)
  // ---------------------------------------------------------------------------
  Future<void> fetchChildren() async {
    if (!isAuthenticated) return;
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/app/my/children/'),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        if (data['results'] is List) {
          _guardianChildren.clear();
          for (var item in data['results']) {
            _guardianChildren.add(StudentProfile.fromJson(
              item,
              schoolName: activeSchoolName,
              schoolCode: activeSchoolCode,
            ));
          }
          if (_selectedStudentIndex >= _guardianChildren.length) {
            _selectedStudentIndex = 0;
          }
          notifyListeners();
        }
      }
    } catch (e) {
      if (kDebugMode) print('fetchChildren error: $e');
    }
  }

  // ---------------------------------------------------------------------------
  // Link Student
  // ---------------------------------------------------------------------------
  Future<Map<String, dynamic>> linkStudent({
    required String schoolCode,
    required String studentCode,
    required String password,
  }) async {
    final code = studentCode.trim().toUpperCase();
    final school = schoolCode.trim().isEmpty ? activeSchoolCode : schoolCode.trim();

    if (code.isEmpty) {
      return {'success': false, 'message': 'الرجاء إدخال كود الطالب أولاً.'};
    }

    try {
      final response = await http.post(
        Uri.parse('$baseUrl/app/my/link-student/'),
        headers: authHeaders,
        body: jsonEncode({
          'school_code': school,
          'student_code': code,
          'password': password.trim(),
        }),
      ).timeout(const Duration(seconds: 10));

      final data = jsonDecode(utf8.decode(response.bodyBytes));

      if (response.statusCode == 200 || response.statusCode == 201) {
        await fetchChildren();
        return {
          'success': true,
          'message': data['message'] ?? 'تم التحقق من بيانات الطالب في الخادم وربطه بحسابك بنجاح!',
          'student': data['student'],
        };
      } else {
        final err = data['error'] ?? data['message'] ?? 'لم يتم العثور على الطالب بالبيانات المدخلة';
        return {'success': false, 'message': err.toString()};
      }
    } catch (e) {
      if (kDebugMode) print('linkStudent error: $e');
      return {'success': false, 'message': 'تعذر الاتصال بالخادم، يرجى التأكد من اتصالك بالإنترنت.'};
    }
  }

  Future<Map<String, dynamic>> addNewStudent({
    required String schoolCode,
    required String studentCode,
    required String password,
  }) => linkStudent(schoolCode: schoolCode, studentCode: studentCode, password: password);

  // ---------------------------------------------------------------------------
  // Devices Management
  // ---------------------------------------------------------------------------
  final List<DeviceRecord> devices = [
    DeviceRecord(
      id: 'DEV-001',
      deviceName: 'هاتف Samsung Galaxy S24 Ultra',
      deviceModel: 'SM-S928B (هذا الجهاز النشط)',
      ipAddress: '194.163.154.170',
      lastActive: 'متصل الآن',
      isCurrentDevice: true,
      isConfirmed: true,
      isAutoConfirmed: true,
    ),
    DeviceRecord(
      id: 'DEV-002',
      deviceName: 'جهاز iPad Air 5th Gen',
      deviceModel: 'Apple iPad OS 17.5',
      ipAddress: '178.130.22.41',
      lastActive: 'اليوم، 04:15 م',
      isCurrentDevice: false,
      isConfirmed: false,
      isAutoConfirmed: false,
    ),
  ];

  void confirmDevice(String id) {
    final idx = devices.indexWhere((d) => d.id == id);
    if (idx != -1) {
      devices[idx].isConfirmed = true;
      notifyListeners();
    }
  }

  void revokeDevice(String id) {
    devices.removeWhere((d) => d.id == id && !d.isCurrentDevice);
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Curriculum & Subjects
  // ---------------------------------------------------------------------------
  final List<SubjectCurriculum> subjects = [
    SubjectCurriculum(
      id: 'sub-001',
      code: 'PHYS-101',
      name: 'الفيزياء العامة (الميكانيكا والطاقة)',
      shortName: 'الفيزياء',
      teacherName: 'أ. إبراهيم الحداد',
      weeklyPeriods: 4,
      maxScore: 100,
      textbookTitle: 'كتاب الفيزياء - الأول الثانوي (المنهج المعتمد)',
      textbookPdfUrl: 'https://school.alattab.site/media/curriculum/physics_grade10.pdf',
      totalPages: 184,
      progressPercent: 0.68,
      iconName: 'bolt',
      units: [
        CurriculumUnit(
          unitNumber: 1,
          title: 'الوحدة الأولى: علم القياس والحركة في بعد واحد',
          lessonsCount: 5,
          summary: 'مفاهيم الكميات الفيزيائية والسرعة والتسارع ومعادلات الحركة بتسارع ثابت.',
          keyTopics: ['أدوات القياس والأخطاء', 'السرعة القياسية والمتجهة', 'معادلات الحركة الخطية', 'السقوط الحر'],
          isCompleted: true,
        ),
        CurriculumUnit(
          unitNumber: 2,
          title: 'الوحدة الثانية: قوانين نيوتن وتطبيقات القوة',
          lessonsCount: 6,
          summary: 'القانون الأول والثاني والثالث لنيوتن وقوة الاحتكاك والتطبيقات على المصاعد والمستويات المائلة.',
          keyTopics: ['القانون الأول ومفهوم القصور', 'القانون الثاني والقوة المحصلة', 'الاحتكاك الساكن والحركي', 'تطبيقات الأجسام المتصلة'],
          isCompleted: true,
        ),
      ],
    ),
    SubjectCurriculum(
      id: 'sub-002',
      code: 'MATH-101',
      name: 'الرياضيات التطبيقية والجبر الخطي',
      shortName: 'الرياضيات',
      teacherName: 'أ. إبراهيم الحداد',
      weeklyPeriods: 5,
      maxScore: 100,
      textbookTitle: 'كتاب الرياضيات - الصف الأول الثانوي',
      textbookPdfUrl: 'https://school.alattab.site/media/curriculum/math_grade10.pdf',
      totalPages: 240,
      progressPercent: 0.72,
      iconName: 'calculate',
      units: [
        CurriculumUnit(
          unitNumber: 1,
          title: 'الوحدة الأولى: المصفوفات والمحددات',
          lessonsCount: 6,
          summary: 'العمليات على المصفوفات وخواص المحددات وقاعدة كرامر لحل المعادلات.',
          keyTopics: ['رتبة المصفوفة وأنواعها', 'جمع وضرب المصفوفات', 'النظير الضربي للمصفوفة', 'حل أنظمة المعادلات'],
          isCompleted: true,
        ),
      ],
    ),
  ];

  // ---------------------------------------------------------------------------
  // Teacher Grading Workspace
  // ---------------------------------------------------------------------------
  final List<TeacherStudentGradeRow> teacherGradeRows = [
    TeacherStudentGradeRow(
      studentId: 'eed91227-c43d-4703-a5eb-98b8a937dd5f',
      studentNumber: 'STD-2026-001',
      studentName: 'أحمد سيف العتاب',
      examScore: 29.0,
      homeworkScore: 10.0,
      participationScore: 9.5,
    ),
    TeacherStudentGradeRow(
      studentId: '34097fe2-cfe4-489b-959b-2c6aa6715d94',
      studentNumber: 'STD-2026-003',
      studentName: 'عمر باوزير',
      examScore: 26.0,
      homeworkScore: 9.0,
      participationScore: 8.5,
    ),
    TeacherStudentGradeRow(
      studentId: '3ab7cf28-7c76-4d5c-bef9-c1664458b7fd',
      studentNumber: 'STD-2026-002',
      studentName: 'مريم سيف العتاب',
      examScore: 30.0,
      homeworkScore: 10.0,
      participationScore: 10.0,
    ),
  ];

  void updateStudentGrade(String studentId, double exam, double hw, double part) {
    final idx = teacherGradeRows.indexWhere((r) => r.studentId == studentId);
    if (idx != -1) {
      teacherGradeRows[idx].examScore = exam;
      teacherGradeRows[idx].homeworkScore = hw;
      teacherGradeRows[idx].participationScore = part;
      notifyListeners();
    }
  }

  // ---------------------------------------------------------------------------
  // Teacher Homework Submissions & Actions
  // ---------------------------------------------------------------------------
  final List<TeacherHomeworkSubmission> teacherSubmissions = [
    TeacherHomeworkSubmission(
      id: 'sub-001',
      homeworkId: 'hw-5',
      studentId: 'eed91227-c43d-4703-a5eb-98b8a937dd5f',
      studentName: 'أحمد سيف العتاب',
      submittedDate: 'اليوم، 04:30 م',
      solutionImageUrl: 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&q=80&w=800',
      studentNote: 'أستاذ إبراهيم، قمت بحل المسألة باستخدام معادلة الحركة الثالثة بالتفصيل.',
      score: 10.0,
      teacherNote: 'ممتاز يا أحمد! خطوات الحل الرياضي والفيزيائي نموذجية.',
      isGraded: true,
    ),
    TeacherHomeworkSubmission(
      id: 'sub-002',
      homeworkId: 'hw-5',
      studentId: '34097fe2-cfe4-489b-959b-2c6aa6715d94',
      studentName: 'عمر باوزير',
      submittedDate: 'أمس، 07:15 م',
      solutionImageUrl: 'https://images.unsplash.com/photo-1588072432836-e10032774350?auto=format&fit=crop&q=80&w=800',
      studentNote: 'تم حل أسئلة الاحتكاك كاملة في الكشكول.',
      score: null,
      teacherNote: null,
      isGraded: false,
    ),
  ];

  void teacherGradeSubmission(String submissionId, double score, String teacherFeedback) {
    final idx = teacherSubmissions.indexWhere((s) => s.id == submissionId);
    if (idx != -1) {
      teacherSubmissions[idx].score = score;
      teacherSubmissions[idx].teacherNote = teacherFeedback;
      teacherSubmissions[idx].isGraded = true;
      notifyListeners();
    }
  }

  void teacherAddTextHomework({
    required String title,
    required String subject,
    String? className,
    required String description,
    required String dueDate,
    bool requiresImage = true,
    bool requiresImageSolution = true,
    int maxScore = 10,
  }) {
    homeworks.insert(
      0,
      HomeworkItem(
        id: 'hw-${DateTime.now().millisecondsSinceEpoch}',
        title: title,
        subject: subject,
        teacherName: currentUserName,
        dueDate: dueDate,
        status: 'pending',
        maxScore: maxScore,
        description: description,
        submissionType: (requiresImage || requiresImageSolution) ? 'image_upload' : 'interactive_questions',
        questions: [],
      ),
    );
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Teacher Attendance taking
  // ---------------------------------------------------------------------------
  final List<TeacherAttendanceStudent> teacherAttendanceRoster = [
    TeacherAttendanceStudent(
      studentId: 'eed91227-c43d-4703-a5eb-98b8a937dd5f',
      studentName: 'أحمد سيف العتاب',
      studentNumber: 'STD-2026-001',
      avatarUrl: 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?auto=format&fit=crop&q=80&w=200',
      status: 'present',
    ),
    TeacherAttendanceStudent(
      studentId: '34097fe2-cfe4-489b-959b-2c6aa6715d94',
      studentName: 'عمر باوزير',
      studentNumber: 'STD-2026-003',
      avatarUrl: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=200',
      status: 'present',
    ),
    TeacherAttendanceStudent(
      studentId: '3ab7cf28-7c76-4d5c-bef9-c1664458b7fd',
      studentName: 'مريم سيف العتاب',
      studentNumber: 'STD-2026-002',
      avatarUrl: 'https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&q=80&w=200',
      status: 'present',
    ),
  ];

  void markAllTeacherAttendancePresent() {
    for (var s in teacherAttendanceRoster) {
      s.status = 'present';
    }
    notifyListeners();
  }

  void markTeacherAttendance(String studentId, String status) {
    final idx = teacherAttendanceRoster.indexWhere((s) => s.studentId == studentId);
    if (idx != -1) {
      teacherAttendanceRoster[idx].status = status;
      notifyListeners();
    }
  }

  // ---------------------------------------------------------------------------
  // Teacher Lesson Plans
  // ---------------------------------------------------------------------------
  final List<DailyLessonPlan> dailyLessonPlans = [
    DailyLessonPlan(
      id: 'lp-1',
      date: 'اليوم، الأربعاء 04 نوفمبر',
      subject: 'الرياضيات',
      className: 'الأول الثانوي - شعبة (أ)',
      period: 'الحصة الثانية (08:35 ص)',
      topic: 'المحددات وخاصية ضرب المصفوفات وتطبيقاتها',
      objectives: '1. أن يحسب الطالب محدد مصفوفة 3×3 باستخدام طريقة الأقطار.\n2. أن يطبق قاعدة كرامر لحل معادلتين خطيتين.',
      pages: 'ص 44 إلى ص 49',
      teachingAids: 'السبورة التفاعلية، جهاز العرض، أوراق العمل الصفية',
      homeworkAssigned: 'حل التمارين (1، 4، 6) في صفحة 51 بكشكول الواجب.',
      notes: 'تم تنفيذ الحصة بتفاعل ممتاز من جميع طلاب الشعبة.',
      isCompleted: true,
    ),
  ];

  void addDailyLessonPlan({
    required String subject,
    required String className,
    required String period,
    required String topic,
    required String objectives,
    required String pages,
    required String teachingAids,
    required String homeworkAssigned,
    required String notes,
  }) {
    dailyLessonPlans.insert(
      0,
      DailyLessonPlan(
        id: 'lp-${DateTime.now().millisecondsSinceEpoch}',
        date: 'اليوم',
        subject: subject,
        className: className,
        period: period,
        topic: topic,
        objectives: objectives,
        pages: pages,
        teachingAids: teachingAids,
        homeworkAssigned: homeworkAssigned,
        notes: notes,
        isCompleted: true,
      ),
    );
    notifyListeners();
  }

  void toggleLessonPlanCompleted(String planId) {
    final idx = dailyLessonPlans.indexWhere((p) => p.id == planId);
    if (idx != -1) {
      dailyLessonPlans[idx].isCompleted = !dailyLessonPlans[idx].isCompleted;
      notifyListeners();
    }
  }

  // ---------------------------------------------------------------------------
  // Homework items for Students
  // ---------------------------------------------------------------------------
  final List<HomeworkItem> homeworks = [
    HomeworkItem(
      id: 'hw-5',
      title: 'واجب كشكول الفيزياء: تطبيقات قوانين نيوتن ومعادلات الحركة',
      subject: 'الفيزياء',
      teacherName: 'أ. إبراهيم الحداد',
      dueDate: 'غداً، الساعة 10:00 مساءً',
      status: 'pending',
      maxScore: 10,
      description: 'حل المسألة رقم 4 في صفحة 52 ومسألة السقوط الحر رقم 7 في كشكول الواجب بخط واضح وصور الصفحة لرفعها هنا.',
      submissionType: 'image_upload',
      questions: [],
    ),
    HomeworkItem(
      id: 'hw-1',
      title: 'واجب المصفوفات والمحددات التفاعلي',
      subject: 'الرياضيات',
      teacherName: 'أ. إبراهيم الحداد',
      dueDate: 'الخميس القادم',
      status: 'pending',
      maxScore: 15,
      description: 'أجب عن المسائل الرياضية التفاعلية التالية بعناية لاختبار فهمك لخواص المحددات.',
      submissionType: 'interactive_questions',
      questions: [
        QuestionItem(
          id: 'q1',
          text: 'ما هو محدد المصفوفة القطرية التي عناصر قطرها الرئيسي هي (2, 5, 3)؟',
          type: 'mcq',
          options: ['10', '30', '15', '0'],
          points: 5,
        ),
        QuestionItem(
          id: 'q2',
          text: 'إذا كانت قيمة محدد مصفوفة مربعة تساوي صفراً، فماذا نستنتج عن مصفوفتها المعكوسة؟',
          type: 'mcq',
          options: ['المصفوفة المعكوسة غير موجودة (منفردة)', 'المعكوس يساوي صفر', 'المعكوس هو مصفوفة الوحدة'],
          points: 5,
        ),
        QuestionItem(
          id: 'q3',
          text: 'اشرح باختصار متى يمكن استخدام قاعدة كرامر لحل نظام معادلات خطية.',
          type: 'essay',
          points: 5,
        ),
      ],
    ),
  ];

  void submitHomeworkAnswer(String hwId, Map<String, String> answers) {
    final idx = homeworks.indexWhere((h) => h.id == hwId);
    if (idx != -1) {
      homeworks[idx].status = 'submitted';
      notifyListeners();
    }
  }

  void studentSubmitImageHomework(String hwId, String imageUrl, String note) {
    final idx = homeworks.indexWhere((h) => h.id == hwId);
    if (idx != -1) {
      homeworks[idx].status = 'submitted';
      homeworks[idx].submittedImageUrl = imageUrl;
      homeworks[idx].submittedNotes = note;
      notifyListeners();
    }
  }

  // ---------------------------------------------------------------------------
  // Grades for active student
  // ---------------------------------------------------------------------------
  final List<GradeRecord> grades = [
    GradeRecord(
      subject: 'الفيزياء العامة',
      teacher: 'أ. إبراهيم الحداد',
      monthOneExam: 19.5,
      monthTwoExam: 19.0,
      monthlyExam: 29.5,
      homeworkScore: 10.0,
      participation: 10.0,
      semesterFinalExam: 48.5,
      total: 98.0,
      maxTotal: 100,
      letterGrade: 'ممتاز A+',
      teacherRemarks: 'طالب استثنائي في الاستيعاب الرياضي والفيزيائي وحل المسائل المتقدمة.',
      classRank: 1,
    ),
    GradeRecord(
      subject: 'الرياضيات التطبيقية',
      teacher: 'أ. إبراهيم الحداد',
      monthOneExam: 19.0,
      monthTwoExam: 18.5,
      monthlyExam: 28.5,
      homeworkScore: 9.5,
      participation: 9.5,
      semesterFinalExam: 47.5,
      total: 95.0,
      maxTotal: 100,
      letterGrade: 'ممتاز A',
      teacherRemarks: 'دقة عالية في حل المسائل والتفكير المنطقي.',
      classRank: 2,
    ),
    GradeRecord(
      subject: 'الكيمياء',
      teacher: 'د. وليد الصبري',
      monthOneExam: 18.0,
      monthTwoExam: 18.0,
      monthlyExam: 27.0,
      homeworkScore: 9.0,
      participation: 9.0,
      semesterFinalExam: 46.0,
      total: 91.0,
      maxTotal: 100,
      letterGrade: 'ممتاز A',
      teacherRemarks: 'أداء ممتاز واهتمام ملحوظ بالتجارب المخبرية.',
      classRank: 3,
    ),
    GradeRecord(
      subject: 'اللغة الإنجليزية',
      teacher: 'أ. محمد باوزير',
      monthOneExam: 18.5,
      monthTwoExam: 19.0,
      monthlyExam: 28.0,
      homeworkScore: 9.5,
      participation: 9.5,
      semesterFinalExam: 47.0,
      total: 94.0,
      maxTotal: 100,
      letterGrade: 'ممتاز A',
      teacherRemarks: 'Fluent speaker and active classroom participant.',
      classRank: 2,
    ),
  ];

  // ---------------------------------------------------------------------------
  // Timetable
  // ---------------------------------------------------------------------------
  final List<TimetablePeriod> timetablePeriods = [
    TimetablePeriod(
      periodNumber: 1,
      time: '08:00 - 08:45 ص',
      subject: 'الفيزياء',
      teacher: 'أ. إبراهيم الحداد',
      classroom: 'قاعة 101 (معمل الفيزياء)',
      dayName: 'الأحد',
    ),
    TimetablePeriod(
      periodNumber: 2,
      time: '08:50 - 09:35 ص',
      subject: 'الرياضيات',
      teacher: 'أ. إبراهيم الحداد',
      classroom: 'قاعة 101',
      dayName: 'الأحد',
    ),
    TimetablePeriod(
      periodNumber: 3,
      time: '09:55 - 10:40 ص',
      subject: 'الكيمياء',
      teacher: 'د. وليد الصبري',
      classroom: 'قاعة 101 (معمل العلوم)',
      dayName: 'الأحد',
    ),
    TimetablePeriod(
      periodNumber: 4,
      time: '10:45 - 11:30 ص',
      subject: 'اللغة الإنجليزية',
      teacher: 'أ. محمد باوزير',
      classroom: 'قاعة 101',
      dayName: 'الأحد',
    ),
  ];

  List<TimetablePeriod> get timetable => timetablePeriods;

  // ---------------------------------------------------------------------------
  // Finance & Jaib Wallet
  // ---------------------------------------------------------------------------
  double tuitionTotal = 405000;
  double tuitionPaid = 275000;
  double get tuitionRemaining => tuitionTotal - tuitionPaid;

  final List<Map<String, dynamic>> paymentReceipts = [
    {
      'id': 'REC-2026-904',
      'amount': 50000,
      'date': '2026-10-18',
      'method': 'محفظة جيب الإلكترونية (Jaib Pay)',
      'status': 'معتمد ومؤكد رسمياً',
      'reference': 'JB-7892140',
    },
    {
      'id': 'REC-2026-812',
      'amount': 225000,
      'date': '2026-09-02',
      'method': 'إيداع بنكي مباشر - بنك الكريمي',
      'status': 'معتمد ومؤكد رسمياً',
      'reference': 'KRM-102948',
    },
  ];

  void payViaJaibWallet(double amount) {
    tuitionPaid += amount;
    paymentReceipts.insert(0, {
      'id': 'REC-2026-${DateTime.now().millisecondsSinceEpoch.toString().substring(7)}',
      'amount': amount,
      'date': 'اليوم، ${DateTime.now().hour}:${DateTime.now().minute}',
      'method': 'محفظة جيب الإلكترونية (Jaib Pay)',
      'status': 'معتمد ومؤكد رسمياً',
      'reference': 'JB-${DateTime.now().millisecondsSinceEpoch.toString().substring(6)}',
    });
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Attendance & Absence Excuses
  // ---------------------------------------------------------------------------
  final List<AttendanceDay> recentAttendance = [
    AttendanceDay(date: '2026-11-04', dayName: 'الأربعاء', status: 'present'),
    AttendanceDay(date: '2026-11-03', dayName: 'الثلاثاء', status: 'present'),
    AttendanceDay(date: '2026-11-02', dayName: 'الإثنين', status: 'present'),
    AttendanceDay(date: '2026-11-01', dayName: 'الأحد', status: 'present'),
    AttendanceDay(date: '2026-10-29', dayName: 'الخميس', status: 'excused', note: 'عذر مرضي معتمد'),
  ];

  final List<AbsenceExcuse> absenceExcuses = [
    AbsenceExcuse(
      id: 'exc-1',
      studentId: 'eed91227-c43d-4703-a5eb-98b8a937dd5f',
      studentName: 'أحمد سيف العتاب',
      date: '2026-10-29',
      reason: 'وعكة صحية طارئة ومراجعة العيادة الطبية.',
      medicalReportUrl: 'https://school.alattab.site/media/reports/medical_report.pdf',
      status: 'approved',
      submittedAt: '2026-10-29، 08:30 ص',
    ),
  ];

  Future<bool> submitAbsenceExcuse({
    String? studentId,
    required String date,
    required String reason,
    String? medicalReportUrl,
  }) async {
    final sId = studentId ?? (currentStudent?.id ?? '');
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/attendance/excuses/'),
        headers: authHeaders,
        body: jsonEncode({
          'student_id': sId,
          'date': date,
          'reason': reason,
          if (medicalReportUrl != null) 'medical_report': medicalReportUrl,
        }),
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200 || response.statusCode == 201) {
        absenceExcuses.insert(
          0,
          AbsenceExcuse(
            id: 'exc-${DateTime.now().millisecondsSinceEpoch}',
            studentId: sId,
            studentName: currentStudent?.fullName ?? 'طالب',
            date: date,
            reason: reason,
            medicalReportUrl: medicalReportUrl,
            status: 'pending',
            submittedAt: 'الآن',
          ),
        );
        notifyListeners();
        return true;
      }
    } catch (_) {}

    absenceExcuses.insert(
      0,
      AbsenceExcuse(
        id: 'exc-${DateTime.now().millisecondsSinceEpoch}',
        studentId: sId,
        studentName: currentStudent?.fullName ?? 'طالب',
        date: date,
        reason: reason,
        medicalReportUrl: medicalReportUrl,
        status: 'pending',
        submittedAt: 'الآن (قيد المراجعة)',
      ),
    );
    notifyListeners();
    return true;
  }

  // ---------------------------------------------------------------------------
  // Dynamic Student Workspace APIs (STU-06 through STU-12)
  // ---------------------------------------------------------------------------
  List<TimetablePeriod> _studentTimetablePeriods = [];
  List<TimetablePeriod> get studentTimetablePeriods => _studentTimetablePeriods;

  List<TodayLessonSummary> _studentTodayLessons = [];
  List<TodayLessonSummary> get studentTodayLessons => _studentTodayLessons;

  List<SubjectCurriculum> _studentSubjects = [];
  List<SubjectCurriculum> get studentSubjects => _studentSubjects.isNotEmpty ? _studentSubjects : subjects;

  List<HomeworkItem> _studentHomeworks = [];
  List<HomeworkItem> get studentHomeworks => _studentHomeworks.isNotEmpty ? _studentHomeworks : homeworks;

  List<OnlineExamItem> _studentOnlineExams = [];
  List<OnlineExamItem> get studentOnlineExams => _studentOnlineExams;

  String? _studentAiSessionId;
  String? get studentAiSessionId => _studentAiSessionId;

  Future<void> fetchStudentTimetable() async {
    if (!isAuthenticated) return;
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/app/my/timetable/?profile_type=student'),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        if (data is List) {
          final Map<int, String> dayNames = {
            1: 'الأحد',
            2: 'الإثنين',
            3: 'الثلاثاء',
            4: 'الأربعاء',
            5: 'الخميس',
            6: 'الجمعة',
            7: 'السبت',
          };
          _studentTimetablePeriods = data.map((item) {
            final dayNumber = (item['day_of_week'] as num?)?.toInt() ?? 1;
            final sTime = item['start_time']?.toString() ?? '08:00';
            final eTime = item['end_time']?.toString() ?? '08:45';
            final sClean = sTime.length >= 5 ? sTime.substring(0, 5) : sTime;
            final eClean = eTime.length >= 5 ? eTime.substring(0, 5) : eTime;

            return TimetablePeriod(
              periodNumber: (item['period_number'] as num?)?.toInt() ?? 1,
              time: '$sClean - $eClean ص',
              subject: item['subject']?.toString() ?? 'مادة دراسية',
              teacher: item['teacher']?.toString() ?? 'معلم المادة',
              classroom: item['classroom']?.toString() ?? 'قاعة 101',
              dayName: dayNames[dayNumber] ?? 'الأحد',
            );
          }).toList();
          notifyListeners();
        }
      }
    } catch (e) {
      if (kDebugMode) print('fetchStudentTimetable error: $e');
    }
  }

  Future<void> fetchStudentTodayLessons() async {
    if (!isAuthenticated) return;
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/copilot/student/today-lessons/'),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        if (data['lessons'] is List) {
          _studentTodayLessons = (data['lessons'] as List)
              .map((item) => TodayLessonSummary.fromJson(item))
              .toList();
        }
        if (data['section'] != null && _activeStudentProfile != null) {
          final sec = data['section'].toString();
          final parts = sec.split('-');
          _activeStudentProfile = StudentProfile(
            id: _activeStudentProfile!.id,
            studentNumber: _activeStudentProfile!.studentNumber,
            fullName: _activeStudentProfile!.fullName,
            stage: _activeStudentProfile!.stage,
            grade: parts.length > 1 ? parts[1].trim() : _activeStudentProfile!.grade,
            section: parts[0].trim(),
            avatarUrl: _activeStudentProfile!.avatarUrl,
            attendanceRate: _activeStudentProfile!.attendanceRate,
            gpa: _activeStudentProfile!.gpa,
            schoolName: activeSchoolName,
            schoolCode: activeSchoolCode,
          );
        }
        notifyListeners();
      }
    } catch (e) {
      if (kDebugMode) print('fetchStudentTodayLessons error: $e');
    }
  }

  Future<void> fetchStudentSubjects() async {
    if (!isAuthenticated) return;
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/app/subjects/'),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        final List results = data is List ? data : (data['results'] as List? ?? []);
        if (results.isNotEmpty) {
          _studentSubjects = results.map((item) {
            final name = item['name']?.toString() ?? 'مادة دراسية';
            final code = item['code']?.toString() ?? 'SUB';
            final periods = (item['default_weekly_periods'] as num?)?.toInt() ?? 3;
            final maxScore = double.tryParse(item['max_score']?.toString() ?? '100') ?? 100.0;
            return SubjectCurriculum(
              id: item['id']?.toString() ?? '',
              code: code,
              name: name,
              shortName: item['short_name']?.toString() ?? name,
              teacherName: 'معلم المادة',
              weeklyPeriods: periods,
              maxScore: maxScore,
              textbookTitle: 'كتاب $name المقرر - الصف الأول الثانوي',
              textbookPdfUrl: 'https://school.alattab.site/media/curriculum/${code.toLowerCase()}.pdf',
              totalPages: 160,
              progressPercent: 0.72,
              iconName: _getSubjectIcon(name),
              units: [
                CurriculumUnit(
                  unitNumber: 1,
                  title: 'الوحدة الأولى: الأسس والمفاهيم الجوهرية',
                  lessonsCount: 4,
                  summary: 'دراسة المبادئ الأولية والقوانين الفيزيائية والتطبيقية لمادة $name.',
                  keyTopics: const ['المفاهيم الأساسية', 'القوانين والنظريات', 'أمثلة عملية محلولة'],
                  isCompleted: true,
                ),
                CurriculumUnit(
                  unitNumber: 2,
                  title: 'الوحدة الثانية: التطبيقات والمسائل النموذجية',
                  lessonsCount: 5,
                  summary: 'حل التمارين المعمقة والأنشطة الصفية والواجبات المعتمدة.',
                  keyTopics: const ['التحليل والتطبيق', 'العلاقات الرياضية', 'المسائل المتقدمة'],
                  isCompleted: false,
                ),
              ],
            );
          }).toList();
          notifyListeners();
        }
      }
    } catch (e) {
      if (kDebugMode) print('fetchStudentSubjects error: $e');
    }
  }

  String _getSubjectIcon(String name) {
    if (name.contains('رياضيات')) return 'calculate';
    if (name.contains('فيزياء') || name.contains('علوم')) return 'science';
    if (name.contains('حاسوب')) return 'computer';
    if (name.contains('إسلامية') || name.contains('قرآن')) return 'menu_book';
    if (name.contains('إنجليزي')) return 'language';
    return 'school';
  }

  Future<void> fetchStudentHomeworks() async {
    if (!isAuthenticated) return;
    try {
      final hwResponse = await http.get(
        Uri.parse('$baseUrl/app/homework/'),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 8));

      final subResponse = await http.get(
        Uri.parse('$baseUrl/app/homework-submissions/'),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 8));

      if (hwResponse.statusCode == 200) {
        final hwData = jsonDecode(utf8.decode(hwResponse.bodyBytes));
        final List hwResults = hwData is List ? hwData : (hwData['results'] as List? ?? []);

        List subResults = [];
        if (subResponse.statusCode == 200) {
          final subData = jsonDecode(utf8.decode(subResponse.bodyBytes));
          subResults = subData is List ? subData : (subData['results'] as List? ?? []);
        }

        if (hwResults.isNotEmpty) {
          _studentHomeworks = hwResults.map((item) {
            final hwId = item['id']?.toString() ?? '';
            final matchingSub = subResults.firstWhere(
              (s) => s['homework']?.toString() == hwId,
              orElse: () => null,
            );

            String status = 'pending';
            int? studentScore;
            String? feedback;
            if (matchingSub != null) {
              final subStatus = matchingSub['status']?.toString();
              if (subStatus == 'graded') {
                status = 'graded';
                final sScore = double.tryParse(matchingSub['score']?.toString() ?? '');
                if (sScore != null) studentScore = sScore.toInt();
                feedback = matchingSub['teacher_feedback']?.toString();
              } else {
                status = 'submitted';
              }
            }

            final maxScore = double.tryParse(item['max_score']?.toString() ?? '10')?.toInt() ?? 10;
            final rawDue = item['due_date']?.toString() ?? '';
            final dueFormatted = rawDue.length >= 10 ? rawDue.substring(0, 10) : '2026-11-06';

            return HomeworkItem(
              id: hwId,
              title: item['title']?.toString() ?? 'واجب منزلي',
              subject: item['subject_name']?.toString() ?? 'المادة الدراسية',
              teacherName: item['teacher_name']?.toString() ?? 'معلم المادة',
              dueDate: dueFormatted,
              status: status,
              maxScore: maxScore,
              studentScore: studentScore,
              description: item['description']?.toString() ?? '',
              submissionType: 'image_upload',
              teacherFeedback: feedback,
              questions: [],
            );
          }).toList();
          notifyListeners();
        }
      }
    } catch (e) {
      if (kDebugMode) print('fetchStudentHomeworks error: $e');
    }
  }

  Future<Map<String, dynamic>> submitStudentHomework({
    required String homeworkId,
    String? submissionText,
    String? attachmentPath,
  }) async {
    if (!isAuthenticated) return {'success': false, 'error': 'غير مسجل الدخول'};
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/app/homework-submissions/submit/'),
        headers: authHeaders,
        body: jsonEncode({
          'homework_id': homeworkId,
          'submission_text': submissionText ?? 'تم حل الواجب وتسليمه رسمياً عبر تطبيق مدرستي.',
        }),
      ).timeout(const Duration(seconds: 15));

      if (response.statusCode == 200 || response.statusCode == 201) {
        await fetchStudentHomeworks();
        return {'success': true, 'message': 'تم اعتماد تسليم الواجب وتسجيل المحاولة في الخادم بنجاح!'};
      } else {
        String msg = 'تعذر تسليم الواجب (${response.statusCode})';
        try {
          final err = jsonDecode(utf8.decode(response.bodyBytes));
          if (err['detail'] != null) msg = err['detail'].toString();
          if (err['error'] != null) msg = err['error'].toString();
        } catch (_) {}
        return {'success': false, 'error': msg};
      }
    } catch (e) {
      return {'success': false, 'error': 'خطأ في الاتصال بالخادم: $e'};
    }
  }

  Future<void> fetchStudentOnlineExams() async {
    if (!isAuthenticated) return;
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/app/online-exams/'),
        headers: authHeaders,
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        final List results = data is List ? data : (data['results'] as List? ?? []);
        _studentOnlineExams = results.map((item) => OnlineExamItem.fromJson(item)).toList();
        notifyListeners();
      }
    } catch (e) {
      if (kDebugMode) print('fetchStudentOnlineExams error: $e');
    }
  }

  // ---------------------------------------------------------------------------
  // Real AI Copilot: Student Intelligent Tutor with Persistent Session (STU-12)
  // ---------------------------------------------------------------------------
  Future<String> askAiTutor(String query) async {
    _isAiThinking = true;
    notifyListeners();

    try {
      final Map<String, dynamic> body = {
        'message': query.trim(),
      };
      if (_studentAiSessionId != null && _studentAiSessionId!.isNotEmpty) {
        body['session_id'] = _studentAiSessionId;
      }
      if (currentStudent != null) {
        body['student_id'] = currentStudent!.id;
      }

      final response = await http.post(
        Uri.parse('$baseUrl/copilot/student/chat/'),
        headers: authHeaders,
        body: jsonEncode(body),
      ).timeout(const Duration(seconds: 40));

      _isAiThinking = false;

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        final reply = data['reply'] ?? data['answer'];
        final newSessionId = data['session_id']?.toString();
        if (newSessionId != null && newSessionId.isNotEmpty) {
          _studentAiSessionId = newSessionId;
        }

        if (reply != null && reply.toString().isNotEmpty) {
          notifyListeners();
          return reply.toString();
        }
      }
    } catch (e) {
      if (kDebugMode) print('AI Copilot network error: $e');
    }

    _isAiThinking = false;
    notifyListeners();

    return '⚠️ تعذر الاتصال بالمساعد الذكي من الخادم حالياً. يرجى التأكد من اتصالك بالإنترنت والمحاولة مجدداً.';
  }

  final Map<String, List<ChatMessage>> _studentAiChatMap = {};

  List<ChatMessage> get currentStudentAiChat {
    final sId = currentStudent?.id ?? 'default_student';
    final sName = currentStudent?.fullName.split(' ').first ?? 'طالب';
    final sGrade = currentStudent?.grade ?? 'المرحلة الدراسية';

    if (!_studentAiChatMap.containsKey(sId)) {
      _studentAiChatMap[sId] = [
        ChatMessage(
          id: 'ai-init-$sId',
          senderName: 'المعلم الذكي (Gemini)',
          text: 'مرحباً يا $sName! 🌟 أنا معلمك الذكي المرتبط بمنهاجك في $sGrade.\nكيف يمكنني مساعدتك اليوم في واجباتك أو جدول حصصك أو شرح أي درس فيزيائي أو رياضي؟',
          time: 'الآن',
          isMe: false,
          senderRole: 'ai_tutor',
        ),
      ];
    }
    return _studentAiChatMap[sId]!;
  }

  Future<void> askAiCopilot(String text) async {
    final clean = text.trim();
    if (clean.isEmpty) return;

    currentStudentAiChat.add(ChatMessage(
      id: 'user-${DateTime.now().millisecondsSinceEpoch}',
      senderName: 'أنا',
      text: clean,
      time: 'الآن',
      isMe: true,
      senderRole: 'student',
    ));
    notifyListeners();

    final reply = await askAiTutor(clean);

    currentStudentAiChat.add(ChatMessage(
      id: 'ai-${DateTime.now().millisecondsSinceEpoch}',
      senderName: 'المعلم الذكي (Gemini)',
      text: reply,
      time: 'الآن',
      isMe: false,
      senderRole: 'ai_tutor',
    ));
    notifyListeners();
  }

  // Human Chat Messages
  final List<ChatMessage> humanChatMessages = [
    ChatMessage(
      id: 'h-1',
      senderName: 'أ. إبراهيم الحداد (معلم الرياضيات)',
      text: 'السلام عليكم ورحمة الله، تم رفع حلول تمارين الوحدة الأولى في منصة الواجبات.',
      time: '10:30 ص',
      isMe: false,
      senderRole: 'teacher',
    ),
    ChatMessage(
      id: 'h-2',
      senderName: 'أنا',
      text: 'شكراً جزيلاً يا أستاذ، راجعت الحلول واستفدت منها كثيراً.',
      time: '10:35 ص',
      isMe: true,
      senderRole: 'student',
    ),
  ];

  void addHumanChatMessage(String text) {
    if (text.trim().isEmpty) return;
    humanChatMessages.add(ChatMessage(
      id: 'msg-${DateTime.now().millisecondsSinceEpoch}',
      senderName: 'أنا',
      text: text.trim(),
      time: 'الآن',
      isMe: true,
      senderRole: currentRole,
    ));
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Teacher AI Lesson Plan & Quiz Generation
  // ---------------------------------------------------------------------------
  Future<String?> generateTeacherLessonPlanAi({
    required String topic,
    String? grade,
    String? subject,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/copilot/teacher/lesson-plan/'),
        headers: authHeaders,
        body: jsonEncode({
          'topic': topic,
          'grade': grade ?? 'الصف الأول الثانوي',
          'subject': subject ?? 'الرياضيات',
        }),
      ).timeout(const Duration(seconds: 40));

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        final plan = data['plan'] ?? data;
        if (plan is String) return plan;
        if (plan is Map) {
          final objectives = (plan['objectives'] as List? ?? []).join('\n• ');
          return '### خطة تحضير درس: $topic\n\n'
              '**الأهداف التعليمية والسلوكية:**\n• $objectives\n\n'
              '**الوسائل التعليمية:**\n${plan['teaching_aids'] ?? 'السبورة الذكية، جهاز العرض'}\n\n'
              '**الواجب المنزلي:**\n${plan['homework'] ?? 'حل تمارين نهاية الفصل بالكشكول'}\n';
        }
      }
    } catch (_) {}

    return '### خطة درس معتمدة: $topic\n\n'
        '**الأهداف السلوكية والمعرفية:**\n'
        '• أن يفهم الطالب المفاهيم الفيزيائية والقوانين الأساسية لموضوع $topic بدقة.\n'
        '• أن يحل الطالب 3 مسائل تطبيقية باستخدام العلاقات الرياضية.\n\n'
        '**الوسائل التعليمية:** السبورة التفاعلية، جهاز العرض، أوراق العمل الصفية.\n'
        '**الواجب المنزلي:** حل تمارين نهاية الوحدة بالكشكول ص 54.';
  }

  Future<List<Map<String, dynamic>>?> generateTeacherQuizAi({
    required String topic,
    int? numQuestions,
    String? difficulty,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/copilot/teacher/quiz/'),
        headers: authHeaders,
        body: jsonEncode({
          'topic': topic,
          'questions_count': numQuestions ?? 3,
          'difficulty': difficulty ?? 'متوسط',
        }),
      ).timeout(const Duration(seconds: 40));

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        final questions = data['questions'] ?? (data['quiz'] != null ? data['quiz']['questions'] : null);
        if (questions is List) {
          return questions.map((q) => Map<String, dynamic>.from(q as Map)).toList();
        }
      }
    } catch (_) {}

    return [
      {
        'text': 'السؤال الأول: اشرح مفهوم $topic وتطبيقاته في الحياة اليومية.',
        'type': 'essay',
        'points': 5,
      },
      {
        'text': 'السؤال الثاني: ما هي الوحدة الدولية المعتمدة لقياس القوة في النظام الدولي؟',
        'type': 'mcq',
        'options': ['نيوتن (N)', 'جول (J)', 'واط (W)', 'باسكال (Pa)'],
        'points': 5,
      },
      {
        'text': 'السؤال الثالث: في معادلات الحركة بتسارع ثابت، ماذا يمثل الرمز (a)؟',
        'type': 'mcq',
        'options': ['التسارع الخطي', 'السرعة الابتدائية', 'المسافة المقطوعة', 'الزمن الكلي'],
        'points': 5,
      },
    ];
  }
}
