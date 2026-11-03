import { palette } from "@/core/theme/tokens";

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
  { id: "child-ahmed", name: "أحمد", grade: "الصف السادس", section: "الشعبة أ", initials: "أ", tint: palette.primaryTint, attendance: "96%", homeworkCount: "2", feesLabel: "متابعة" },
  { id: "child-mohammed", name: "محمد", grade: "الصف الرابع", section: "الشعبة ب", initials: "م", tint: palette.successTint, attendance: "98%", homeworkCount: "1", feesLabel: "منتظمة" },
  { id: "child-omar", name: "عمر", grade: "الصف الثاني", section: "الشعبة أ", initials: "ع", tint: palette.warningTint, attendance: "94%", homeworkCount: "3", feesLabel: "متابعة" },
];

export const previewClasses: PreviewClass[] = [
  {
    id: "class-grade-six-a", grade: "الصف السادس", section: "الشعبة أ", subject: "الرياضيات", studentCount: 18, tint: palette.primaryTint,
    students: [
      { id: "st-1", name: "أحمد", initials: "أ", tint: palette.primaryTint },
      { id: "st-2", name: "محمد", initials: "م", tint: palette.successTint },
      { id: "st-3", name: "علي", initials: "ع", tint: palette.roseTint },
      { id: "st-4", name: "عمر", initials: "ع", tint: palette.warningTint },
      { id: "st-5", name: "خالد", initials: "خ", tint: palette.violetTint },
      { id: "st-6", name: "سعيد", initials: "س", tint: palette.skyTint },
    ],
  },
  {
    id: "class-grade-five-b", grade: "الصف الخامس", section: "الشعبة ب", subject: "الرياضيات", studentCount: 14, tint: palette.successTint,
    students: [
      { id: "st-7", name: "حسن", initials: "ح", tint: palette.successTint },
      { id: "st-8", name: "ياسر", initials: "ي", tint: palette.primaryTint },
      { id: "st-9", name: "أنس", initials: "أ", tint: palette.warningTint },
      { id: "st-10", name: "مازن", initials: "م", tint: palette.roseTint },
    ],
  },
  {
    id: "class-grade-four-a", grade: "الصف الرابع", section: "الشعبة أ", subject: "العلوم", studentCount: 10, tint: palette.warningTint,
    students: [
      { id: "st-11", name: "زياد", initials: "ز", tint: palette.primaryTint },
      { id: "st-12", name: "رامي", initials: "ر", tint: palette.successTint },
      { id: "st-13", name: "فارس", initials: "ف", tint: palette.warningTint },
    ],
  },
];

export const previewLessons = [
  { id: "lesson-1", time: "08:00", subject: "الرياضيات", teacher: "أ. خالد", room: "قاعة ١" },
  { id: "lesson-2", time: "09:00", subject: "اللغة العربية", teacher: "أ. أحمد", room: "قاعة ٢" },
  { id: "lesson-3", time: "10:00", subject: "العلوم", teacher: "أ. سامي", room: "مختبر العلوم" },
];
