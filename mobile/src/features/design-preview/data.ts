export type PreviewChild = {
  id: string;
  name: string;
  grade: string;
  section: string;
  initials: string;
  tint: string;
  attendance: string;
  homeworkCount: string;
  feesLabel: string;
};

export type PreviewStudent = { id: string; name: string; initials: string; tint: string };

export type PreviewClass = {
  id: string;
  grade: string;
  section: string;
  subject: string;
  studentCount: number;
  tint: string;
  students: PreviewStudent[];
};

export const previewChildren: PreviewChild[] = [
  { id: "child-ahmed", name: "أحمد", grade: "الصف السادس", section: "الشعبة أ", initials: "أ", tint: "#E8F0FF", attendance: "96%", homeworkCount: "2", feesLabel: "متابعة" },
  { id: "child-mohammed", name: "محمد", grade: "الصف الرابع", section: "الشعبة ب", initials: "م", tint: "#E6F5EE", attendance: "98%", homeworkCount: "1", feesLabel: "منتظمة" },
  { id: "child-omar", name: "عمر", grade: "الصف الثاني", section: "الشعبة أ", initials: "ع", tint: "#FFF1E2", attendance: "94%", homeworkCount: "3", feesLabel: "متابعة" },
];

export const previewClasses: PreviewClass[] = [
  {
    id: "class-grade-six-a", grade: "الصف السادس", section: "الشعبة أ", subject: "الرياضيات", studentCount: 18, tint: "#E8F0FF",
    students: [
      { id: "st-1", name: "أحمد", initials: "أ", tint: "#E8F0FF" },
      { id: "st-2", name: "محمد", initials: "م", tint: "#E6F5EE" },
      { id: "st-3", name: "علي", initials: "ع", tint: "#FCE8F0" },
      { id: "st-4", name: "عمر", initials: "ع", tint: "#FFF1E2" },
      { id: "st-5", name: "خالد", initials: "خ", tint: "#EEE9FF" },
      { id: "st-6", name: "سعيد", initials: "س", tint: "#E4F1F5" },
    ],
  },
  {
    id: "class-grade-five-b", grade: "الصف الخامس", section: "الشعبة ب", subject: "الرياضيات", studentCount: 14, tint: "#E6F5EE",
    students: [
      { id: "st-7", name: "حسن", initials: "ح", tint: "#E6F5EE" },
      { id: "st-8", name: "ياسر", initials: "ي", tint: "#E8F0FF" },
      { id: "st-9", name: "أنس", initials: "أ", tint: "#FFF1E2" },
      { id: "st-10", name: "مازن", initials: "م", tint: "#FCE8F0" },
    ],
  },
  {
    id: "class-grade-four-a", grade: "الصف الرابع", section: "الشعبة أ", subject: "العلوم", studentCount: 10, tint: "#FFF1E2",
    students: [
      { id: "st-11", name: "زياد", initials: "ز", tint: "#E8F0FF" },
      { id: "st-12", name: "رامي", initials: "ر", tint: "#E6F5EE" },
      { id: "st-13", name: "فارس", initials: "ف", tint: "#FFF1E2" },
    ],
  },
];

export const previewLessons = [
  { id: "lesson-1", time: "08:00", subject: "الرياضيات", teacher: "أ. خالد", room: "قاعة ١" },
  { id: "lesson-2", time: "09:00", subject: "اللغة العربية", teacher: "أ. أحمد", room: "قاعة ٢" },
  { id: "lesson-3", time: "10:00", subject: "العلوم", teacher: "أ. سامي", room: "مختبر العلوم" },
];
