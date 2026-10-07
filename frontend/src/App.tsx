import { FormEvent, ReactElement, useEffect, useMemo, useState } from 'react';
import './App.css';

type Role = 'SUPER_ADMIN' | 'ADMIN' | 'TEACHER' | 'STUDENT' | 'ACADEMIC_OFFICER';

type AuthenticatedUser = {
  id: number;
  username: string;
  name: string;
  role: Role;
};

type ManagedUser = {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: Role;
  phone_number: string;
  is_active: boolean;
};

type AuditLogRecord = { id: number; actor_name: string; action: string; model_name: string; description: string; created_at: string };
type PerformanceSubject = { code: string; name: string; average_marks: number; total_students: number };
type EnrollmentForm = { student_id: string; school_class_id: string; academic_year_id: string; term_id: string };
const emptyEnrollmentForm: EnrollmentForm = { student_id: '', school_class_id: '', academic_year_id: '', term_id: '' };

type UserForm = Omit<ManagedUser, 'id' | 'is_active'> & { password: string };

type StudentSummary = {
  name: string;
  average: number;
  admission_number: string;
};

const emptyUserForm: UserForm = {
  username: '',
  first_name: '',
  last_name: '',
  email: '',
  role: 'STUDENT',
  phone_number: '',
  password: '',
};

type StudentRecord = {
  id: number;
  full_name: string;
  user?: { first_name?: string; last_name?: string; username?: string; email?: string; phone_number?: string };
  admission_number: string;
  current_class: string;
  date_of_birth: string | null;
  gender: string;
  parent_name: string;
};

type TeacherRecord = { id: number; full_name: string; user: { username: string; first_name: string; last_name: string; email: string; phone_number: string }; employee_id: string; department: string; qualification: string; phone_number: string };
type TeacherProfile = TeacherRecord & { account: { username: string; email: string; role: Role; is_active: boolean; date_joined: string; last_login: string | null } };
type AccountProfile = { id: number; username: string; name: string; email?: string; role: Role };
type SchoolClassRecord = { id: number; name: string; section: string; academic_year: AcademicYearOption; teacher: string | null; teacher_id: number | null; is_active: boolean };
type ManagedSubjectRecord = { id: number; code: string; name: string; school_class: { id: number; name: string; academic_year: AcademicYearOption }; teacher: string | null; teacher_id: number | null; description: string };

type DataManagementForm = {
  username: string; password: string; first_name: string; last_name: string; email: string; phone_number: string;
  admission_number: string; date_of_birth: string; gender: string; current_class: string;
  employee_id: string; department: string; qualification: string;
  name: string; section: string; academic_year_id: string; teacher_id: string; is_active: boolean;
  code: string; school_class_id: string; description: string;
};
const emptyDataManagementForm: DataManagementForm = {
  username: '', password: '', first_name: '', last_name: '', email: '', phone_number: '',
  admission_number: '', date_of_birth: '', gender: '', current_class: '',
  employee_id: '', department: '', qualification: '', name: '', section: '', academic_year_id: '',
  teacher_id: '', is_active: true, code: '', school_class_id: '', description: '',
};

type ResultRecord = {
  id: number;
  marks: number;
  grade: string;
  status: string;
  assessment_type?: string;
  remarks?: string;
  subject?: { id: number; name?: string; code?: string; school_class?: { id: number; name?: string } };
  student?: { id: number; full_name?: string; admission_number?: string };
  academic_year?: { id: number; name?: string };
  term?: { id: number; name?: string };
  entered_by?: { name?: string; username?: string };
  approved_by?: { name?: string; username?: string } | null;
  approvals?: { id: number; decision: string; comments: string; approved_by_name: string; created_at: string }[];
};

type StudentAcademicReport = {
  school_name: string;
  student: { name: string; admission_number: string; class_name: string };
  academic_year: string;
  term: string;
  subjects: { subject: string; marks: number; grade: string; remarks: string }[];
  average: number | null;
  overall_grade: string | null;
  overall_status: string;
  position: number | null;
  class_size: number;
  class_teacher: string;
  academic_officer: string;
  approved_by: string;
  approved_at: string | null;
  published_by: string;
  published_at: string | null;
};

type AcademicYearOption = { id: number; name: string; start_date?: string; end_date?: string; is_active?: boolean };
type ManagedAcademicYear = { id: number; name: string; start_date: string; end_date: string; is_active: boolean };
type AcademicYearForm = Omit<ManagedAcademicYear, 'id'>;
const emptyAcademicYearForm: AcademicYearForm = { name: '', start_date: '', end_date: '', is_active: true };
type TermOption = { id: number; name: string; academic_year: { id: number; name?: string; start_date?: string; end_date?: string }; start_date?: string; end_date?: string; is_active?: boolean };
type ManagedTerm = { id: number; name: string; academic_year: { id: number; name: string; start_date: string; end_date: string }; start_date: string; end_date: string; is_active: boolean };
type TermForm = { academic_year_id: string; name: string; start_date: string; end_date: string; is_active: boolean };
const emptyTermForm: TermForm = { academic_year_id: '', name: '', start_date: '', end_date: '', is_active: false };
type SubjectOption = { id: number; code: string; name: string; school_class: { id: number; name: string } };
type EnrollmentOption = { student: { id: number; full_name: string; admission_number: string }; school_class: { id: number }; academic_year: { id: number }; term: { id: number } };
type ResultForm = { student_id: string; subject_id: string; academic_year_id: string; term_id: string; assessment_type: string; marks: string; remarks: string };
type DashboardNotification = { title: string; message: string; count: number; section: string; status_filter: string };

const emptyResultForm: ResultForm = { student_id: '', subject_id: '', academic_year_id: '', term_id: '', assessment_type: 'CAT', marks: '', remarks: '' };

type DashboardData = {
  stats: {
    students: number;
    teachers: number;
    classes: number;
    subjects: number;
    approved_results: number;
    pending_results: number;
    published_results: number;
    average_performance: number | null;
  };
  school_name: string;
  academic_context: { academic_year: string | null; term: string | null };
  result_status: { draft: number; submitted: number; under_review: number; approved: number; rejected: number; published: number };
  notifications: DashboardNotification[];
  recent_results: ResultRecord[];
  top_students: StudentSummary[];
};

const apiRoot = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

function getSafeErrorMessage(error: Error): string {
  return error.name === 'TypeError'
    ? 'Unable to connect to the school server. Check your connection and try again.'
    : error.message;
}

const roleOptions: { role: Role; label: string; detail: string; icon: string }[] = [
  { role: 'SUPER_ADMIN', label: 'Super Admin', detail: 'System-wide access and security', icon: 'S' },
  { role: 'ADMIN', label: 'Administrator', detail: 'Manage users, classes, subjects and academic years', icon: 'A' },
  { role: 'TEACHER', label: 'Teacher', detail: 'Enter and update marks for assigned subjects', icon: 'T' },
  { role: 'STUDENT', label: 'Student', detail: 'View your own published results', icon: 'S' },
  { role: 'ACADEMIC_OFFICER', label: 'Head / Academic Officer', detail: 'Review results and view school reports', icon: 'H' },
];

const sidebarIconShapes: Record<string, ReactElement> = {
  Dashboard: <><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></>,
  'Data Management': <><path d="M4 7.5h16v12a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 19.5z" /><path d="M3 7.5 5 3h14l2 4.5M8 11v2m4-2v2m4-2v2" /></>,
  Students: <><circle cx="9" cy="8" r="3.2" /><path d="M3.5 20v-1.2A4.8 4.8 0 0 1 8.3 14h1.4a4.8 4.8 0 0 1 4.8 4.8V20zM16 5.2a3.2 3.2 0 0 1 0 6.1M17 14.2a4.8 4.8 0 0 1 3.5 4.6V20" /></>,
  Teachers: <><circle cx="12" cy="7.5" r="3.5" /><path d="M5 20v-1.4a7 7 0 0 1 14 0V20zM18 4l1.3 1.3L22 2.8" /></>,
  Classes: <><path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-5h6v5M8 9h.01M12 9h.01M16 9h.01M8 12h.01M12 12h.01M16 12h.01" /></>,
  Subjects: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 1 4 17.5z" /><path d="M4 16.5A2.5 2.5 0 0 1 6.5 14H20M8 7h8M8 10h6" /></>,
  'Academic Settings': <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18M8 14h2m4 0h2m-8 3h2" /></>,
  'Academic Years': <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18M8 14h3m-3 3h7" /></>,
  Terms: <><rect x="4" y="4" width="16" height="17" rx="2" /><path d="M8 2v4m8-4v4M4 9h16m-11 4h2m3 0h2m-7 4h2" /></>,
  Results: <><path d="M7 3h8l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" /><path d="M15 3v5h5M9 14l2 2 4-4" /></>,
  Reports: <><path d="M4 20V10m5 10V4m5 16v-7m5 7V7M2 20h20" /></>,
  Users: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z" /><path d="m9 11 2 2 4-4" /></>,
  'Users & Access': <><circle cx="9" cy="8" r="3" /><path d="M3.5 20v-1a5.5 5.5 0 0 1 11 0v1zM16 11h5m-2.5-2.5v5" /></>,
  'Audit Logs': <><path d="M3 12a9 9 0 1 0 2.6-6.4L3 8" /><path d="M3 3v5h5m4-1v5l3 2" /></>,
  'My Profile': <><circle cx="12" cy="8" r="3.5" /><path d="M5 21v-1.5a7 7 0 0 1 14 0V21z" /></>,
  'My Results': <><path d="M7 3h8l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" /><path d="M15 3v5h5M9 13h6m-6 3h6" /></>,
  'My Performance': <><path d="M3 19h18M5 16l4-5 3 2 6-8" /><path d="M15 5h3v3" /></>,
  'Result Slip': <><path d="M7 3h8l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" /><path d="M15 3v5h5M9 13h6m-6 3h6m-6 3h4" /></>,
  'My Classes': <><path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-5h6v5M8 9h.01M12 9h.01M16 9h.01" /></>,
  'My Subjects': <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 1 4 17.5z" /><path d="M4 16.5A2.5 2.5 0 0 1 6.5 14H20M8 7h8M8 10h6" /></>,
  'Enter Results': <><path d="M7 3h8l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" /><path d="M15 3v5h5M9 13h6m-6 4h3" /></>,
  'Submitted Results': <><path d="M7 3h8l4 4v14H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" /><path d="M15 3v5h5m-11 5h6m-6 3h6m-6 3h3" /></>,
};

function SidebarIcon({ name }: { name: string }) {
  return <svg className="nav-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{sidebarIconShapes[name] || sidebarIconShapes.Dashboard}</svg>;
}

function SchoolLogo() {
  return <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
    <path d="M24 4 42 11v12c0 11-7.6 17.5-18 21C13.6 40.5 6 34 6 23V11z" fill="rgba(255,255,255,.12)" stroke="currentColor" strokeWidth="2" />
    <path d="m12 17 12-6 12 6-12 6z" fill="currentColor" />
    <path d="M16 20v7c4 3 12 3 16 0v-7l-8 4zM36 18v8" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    <circle cx="36" cy="28" r="1.5" fill="currentColor" />
  </svg>;
}

const roleAccess: Record<Role, string[]> = {
  SUPER_ADMIN: ['Dashboard', 'Students', 'Teachers', 'Classes', 'Subjects', 'Academic Years', 'Terms', 'Results', 'Reports', 'Users', 'Audit Logs'],
  ADMIN: ['Dashboard', 'Students', 'Teachers', 'Classes', 'Subjects', 'Academic Years', 'Terms', 'Results', 'Reports', 'Users', 'Audit Logs'],
  TEACHER: ['Dashboard', 'Students', 'My Classes', 'My Subjects', 'Enter Results', 'Submitted Results', 'Reports'],
  STUDENT: ['Dashboard', 'My Profile', 'My Results', 'My Performance', 'Result Slip'],
  ACADEMIC_OFFICER: ['Dashboard', 'Students', 'Teachers', 'Classes', 'Subjects', 'Terms', 'Results', 'Reports', 'Audit Logs'],
};
const studentWorkspaceItems = ['My Profile', 'My Results', 'My Performance', 'Result Slip'];

const emptyDashboard: DashboardData = {
  stats: { students: 0, teachers: 0, classes: 0, subjects: 0, approved_results: 0, pending_results: 0, published_results: 0, average_performance: null },
  school_name: '',
  academic_context: { academic_year: null, term: null },
  result_status: { draft: 0, submitted: 0, under_review: 0, approved: 0, rejected: 0, published: 0 },
  notifications: [],
  recent_results: [],
  top_students: [],
};

async function readResponse<T>(response: Response): Promise<T> {
  const raw = await response.text();
  let payload: unknown = {};
  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch {
      if (response.ok) {
        throw new Error(`The server returned an unexpected response (${response.status} ${response.statusText}).`);
      }
    }
  }
  if (!response.ok) {
    if (response.status >= 500) {
      throw new Error('Something went wrong. Please try again.');
    }
    const collectMessages = (value: unknown): string[] => {
      if (typeof value === 'string') return [value];
      if (Array.isArray(value)) return value.flatMap(collectMessages);
      if (value && typeof value === 'object') return Object.values(value).flatMap(collectMessages);
      return [];
    };
    const messages = collectMessages(payload);
    throw new Error(messages.join(' ') || 'The request could not be completed. Please check the information and try again.');
  }
  return payload as T;
}

function getCsrfToken(): string {
  const cookie = document.cookie
    .split('; ')
    .find((part) => part.startsWith('csrftoken='));
  return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
}

async function readApi<T>(path: string, signal?: AbortSignal): Promise<T> {
  try {
    const response = await fetch(`${apiRoot}${path}`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal,
    });
    return await readResponse<T>(response);
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    if (error instanceof Error && error.name !== 'TypeError') throw error;
    throw new Error('Unable to connect to the school server. Check your connection and try again.');
  }
}

function formatTermName(name: string): string {
  return name
    .replace(/semist[ae]r/gi, 'Semester')
    .replace(/(semester|term|quarter)(\d)/gi, '$1 $2')
    .replace(/\b(\w)/g, (c) => c.toUpperCase())
    .trim();
}

function App() {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [authError, setAuthError] = useState('');
  const [forgotPasswordView, setForgotPasswordView] = useState(false);
  const [resetToken, setResetToken] = useState('');
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotNotice, setForgotNotice] = useState('');
  const [isSendingReset, setIsSendingReset] = useState(false);
  const [newResetPassword, setNewResetPassword] = useState('');
  const [isResettingPassword, setIsResettingPassword] = useState(false);
  const [resetNotice, setResetNotice] = useState('');
  const [resetDone, setResetDone] = useState(false);
  const [dashboard, setDashboard] = useState<DashboardData>(emptyDashboard);
  const [dashboardError, setDashboardError] = useState('');
  const [isLoadingDashboard, setIsLoadingDashboard] = useState(false);
  const [activeSection, setActiveSection] = useState('Dashboard');
  const [studentWorkspaceView, setStudentWorkspaceView] = useState('My Profile');
  const [teacherResultsView, setTeacherResultsView] = useState('Enter Results');
  const [students, setStudents] = useState<StudentRecord[]>([]);
  const [studentSearch, setStudentSearch] = useState('');
  const [studentClassFilter, setStudentClassFilter] = useState('');
  const [selectedStudent, setSelectedStudent] = useState<StudentRecord | null>(null);
  const [studentResults, setStudentResults] = useState<ResultRecord[]>([]);
  const [studentAcademicReport, setStudentAcademicReport] = useState<StudentAcademicReport | null>(null);
  const [studentReportError, setStudentReportError] = useState('');
  const [isLoadingStudentReport, setIsLoadingStudentReport] = useState(false);
  const [studentResultYearFilter, setStudentResultYearFilter] = useState('');
  const [studentResultTermFilter, setStudentResultTermFilter] = useState('');
  const [studentPageError, setStudentPageError] = useState('');
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);
  const [teacherClasses, setTeacherClasses] = useState<SchoolClassRecord[]>([]);
  const [teacherSubjects, setTeacherSubjects] = useState<ManagedSubjectRecord[]>([]);
  const [teacherClassesError, setTeacherClassesError] = useState('');
  const [isLoadingTeacherClasses, setIsLoadingTeacherClasses] = useState(false);
  const [teacherProfile, setTeacherProfile] = useState<TeacherProfile | null>(null);
  const [accountProfile, setAccountProfile] = useState<AccountProfile | null>(null);
  const [profileError, setProfileError] = useState('');
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passwordChangeError, setPasswordChangeError] = useState('');
  const [passwordChangeNotice, setPasswordChangeNotice] = useState('');
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [showEnrollmentForm, setShowEnrollmentForm] = useState(false);
  const [enrollmentForm, setEnrollmentForm] = useState<EnrollmentForm>(emptyEnrollmentForm);
  const [enrollmentError, setEnrollmentError] = useState('');
  const [isSavingEnrollment, setIsSavingEnrollment] = useState(false);
  const [enrollmentOptionsError, setEnrollmentOptionsError] = useState('');
  const [managedUsers, setManagedUsers] = useState<ManagedUser[]>([]);
  const [userManagementError, setUserManagementError] = useState('');
  const [userManagementNotice, setUserManagementNotice] = useState('');
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [auditLogError, setAuditLogError] = useState('');
  const [isLoadingAuditLogs, setIsLoadingAuditLogs] = useState(false);
  const [auditActionFilter, setAuditActionFilter] = useState('');
  const [auditModelFilter, setAuditModelFilter] = useState('');
  const [auditLimit, setAuditLimit] = useState('100');
  const [reportSubjects, setReportSubjects] = useState<PerformanceSubject[]>([]);
  const [reportError, setReportError] = useState('');
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [isSavingUser, setIsSavingUser] = useState(false);
  const [showUserForm, setShowUserForm] = useState(false);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [userForm, setUserForm] = useState<UserForm>(emptyUserForm);
  const [resultRows, setResultRows] = useState<ResultRecord[]>([]);
  const [resultStatusFilter, setResultStatusFilter] = useState('');
  const [resultError, setResultError] = useState('');
  const [resultNotice, setResultNotice] = useState('');
  const [resultOptionsError, setResultOptionsError] = useState('');
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [isSavingResult, setIsSavingResult] = useState(false);
  const [resultForm, setResultForm] = useState<ResultForm>(emptyResultForm);
  const [editingResultId, setEditingResultId] = useState<number | null>(null);
  const [bulkRows, setBulkRows] = useState<{ student_id: number; name: string; admission: string; marks: string; remarks: string }[]>([]);
  const [bulkContext, setBulkContext] = useState({ academic_year_id: '', term_id: '', subject_id: '', assessment_type: 'CAT' });
  const [bulkError, setBulkError] = useState('');
  const [bulkNotice, setBulkNotice] = useState('');
  const [isSavingBulk, setIsSavingBulk] = useState(false);
  // Bulk approval
  const [bulkApprovalIds, setBulkApprovalIds] = useState<Set<number>>(new Set());
  const [bulkApprovalComments, setBulkApprovalComments] = useState('');
  const [isBulkApproving, setIsBulkApproving] = useState(false);
  const [bulkApprovalError, setBulkApprovalError] = useState('');
  const [bulkApprovalNotice, setBulkApprovalNotice] = useState('');
  // Bulk enrollment
  const [showBulkEnrollForm, setShowBulkEnrollForm] = useState(false);
  const [bulkEnrollIds, setBulkEnrollIds] = useState<Set<number>>(new Set());
  const [bulkEnrollContext, setBulkEnrollContext] = useState({ academic_year_id: '', school_class_id: '', term_id: '' });
  const [isSavingBulkEnroll, setIsSavingBulkEnroll] = useState(false);
  const [bulkEnrollError, setBulkEnrollError] = useState('');
  const [bulkEnrollNotice, setBulkEnrollNotice] = useState('');
  // Bulk user import
  const [showBulkImport, setShowBulkImport] = useState(false);
  const [bulkImportRole, setBulkImportRole] = useState<'STUDENT' | 'TEACHER'>('STUDENT');
  const [bulkImportCsv, setBulkImportCsv] = useState('');
  const [isBulkImporting, setIsBulkImporting] = useState(false);
  const [bulkImportError, setBulkImportError] = useState('');
  const [bulkImportNotice, setBulkImportNotice] = useState('');
  const [reviewComments, setReviewComments] = useState<Record<number, string>>({});
  const [resultYears, setResultYears] = useState<AcademicYearOption[]>([]);
  const [resultTerms, setResultTerms] = useState<TermOption[]>([]);
  const [resultSubjects, setResultSubjects] = useState<SubjectOption[]>([]);
  const [resultEnrollments, setResultEnrollments] = useState<EnrollmentOption[]>([]);
  const [managedAcademicYears, setManagedAcademicYears] = useState<ManagedAcademicYear[]>([]);
  const [academicYearForm, setAcademicYearForm] = useState<AcademicYearForm>(emptyAcademicYearForm);
  const [editingAcademicYearId, setEditingAcademicYearId] = useState<number | null>(null);
  const [showAcademicYearForm, setShowAcademicYearForm] = useState(false);
  const [academicYearError, setAcademicYearError] = useState('');
  const [academicYearNotice, setAcademicYearNotice] = useState('');
  const [isLoadingAcademicYears, setIsLoadingAcademicYears] = useState(false);
  const [isSavingAcademicYear, setIsSavingAcademicYear] = useState(false);
  const [managedTerms, setManagedTerms] = useState<ManagedTerm[]>([]);
  const [termForm, setTermForm] = useState<TermForm>(emptyTermForm);
  const [editingTermId, setEditingTermId] = useState<number | null>(null);
  const [showTermForm, setShowTermForm] = useState(false);
  const [termError, setTermError] = useState('');
  const [termNotice, setTermNotice] = useState('');
  const [isLoadingTerms, setIsLoadingTerms] = useState(false);
  const [isSavingTerm, setIsSavingTerm] = useState(false);
  const [managedTeachers, setManagedTeachers] = useState<TeacherRecord[]>([]);
  const [managedClasses, setManagedClasses] = useState<SchoolClassRecord[]>([]);
  const [managedSubjects, setManagedSubjects] = useState<ManagedSubjectRecord[]>([]);
  const [dataManagementForm, setDataManagementForm] = useState<DataManagementForm>(emptyDataManagementForm);
  const [showDataManagementForm, setShowDataManagementForm] = useState(false);
  const [editingDataRecordId, setEditingDataRecordId] = useState<number | null>(null);
  const [dataManagementError, setDataManagementError] = useState('');
  const [dataManagementNotice, setDataManagementNotice] = useState('');
  const [isLoadingDataManagement, setIsLoadingDataManagement] = useState(false);
  const [isSavingDataManagement, setIsSavingDataManagement] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('reset_token');
    if (token) {
      setResetToken(token);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    fetch(`${apiRoot}/auth/me/`, { credentials: 'include', headers: { Accept: 'application/json' } })
      .then(async (response) => {
        if (response.status === 401) return null;
        return readResponse<{ user: AuthenticatedUser }>(response);
      })
      .then((payload) => {
        if (isMounted && payload) setUser(payload.user);
      })
      .catch(() => {
        if (isMounted) setAuthError('Unable to connect to the school server. Check that the backend is running.');
      })
      .finally(() => {
        if (isMounted) setIsCheckingSession(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!user) return;

    let isMounted = true;
    setIsLoadingDashboard(true);
    setDashboardError('');
    fetch(`${apiRoot}/dashboard/`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    })
      .then((response) => readResponse<DashboardData>(response))
      .then((payload) => {
        if (isMounted) setDashboard({
          ...emptyDashboard,
          ...payload,
          academic_context: payload.academic_context ?? emptyDashboard.academic_context,
          school_name: payload.school_name || '',
          stats: { ...emptyDashboard.stats, ...payload.stats },
          result_status: { ...emptyDashboard.result_status, ...payload.result_status },
          notifications: payload.notifications ?? [],
        });
      })
      .catch((error: Error) => {
        if (isMounted) setDashboardError(getSafeErrorMessage(error));
      })
      .finally(() => {
        if (isMounted) setIsLoadingDashboard(false);
      });

    return () => {
      isMounted = false;
    };
  }, [user]);

  useEffect(() => {
    if (!user || activeSection !== 'Students') return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setIsLoadingStudents(true);
      setStudentPageError('');
      const params = new URLSearchParams();
      if (studentSearch.trim()) params.set('q', studentSearch.trim());
      if (studentClassFilter) params.set('class_id', studentClassFilter);
      fetch(`${apiRoot}/students/?${params.toString()}`, {
        credentials: 'include',
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      })
        .then((response) => readResponse<StudentRecord[]>(response))
        .then((payload) => {
          setStudents(payload);
          if (user.role === 'STUDENT' && payload.length) setSelectedStudent(payload[0]);
        })
        .catch((error: Error) => {
          if (error.name !== 'AbortError') setStudentPageError(getSafeErrorMessage(error));
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsLoadingStudents(false);
        });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [user, activeSection, studentSearch, studentClassFilter]);

  useEffect(() => {
    if (!user || activeSection !== 'Students') return;
    const controller = new AbortController();
    Promise.all([
      readApi<AcademicYearOption[]>('/academic-years/', controller.signal),
      readApi<TermOption[]>('/terms/', controller.signal),
    ])
      .then(([years, terms]) => {
        setResultYears(years);
        setResultTerms(terms);
      })
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setStudentPageError(getSafeErrorMessage(error));
      });
    return () => controller.abort();
  }, [user, activeSection]);

  useEffect(() => {
    if (!user || !['My Classes', 'My Subjects'].includes(activeSection)) return;
    const controller = new AbortController();
    setIsLoadingTeacherClasses(true);
    setTeacherClassesError('');
    const request = activeSection === 'My Classes'
      ? readApi<SchoolClassRecord[]>('/my/classes/', controller.signal).then((payload) => setTeacherClasses(payload))
      : readApi<ManagedSubjectRecord[]>('/subjects/', controller.signal).then((payload) => setTeacherSubjects(payload));
    request
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setTeacherClassesError(getSafeErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingTeacherClasses(false);
      });
    return () => controller.abort();
  }, [user, activeSection]);

  useEffect(() => {
    if (!user || !['Profile', 'Account Settings'].includes(activeSection)) return;
    const controller = new AbortController();
    setIsLoadingProfile(true);
    setProfileError('');
    readApi<TeacherProfile | AccountProfile>('/my/profile/', controller.signal)
      .then((profile) => {
        if (user.role === 'TEACHER') setTeacherProfile(profile as TeacherProfile);
        else setAccountProfile(profile as AccountProfile);
      })
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setProfileError(getSafeErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingProfile(false);
      });
    if (user.role === 'TEACHER') {
      Promise.all([
        readApi<SchoolClassRecord[]>('/my/classes/', controller.signal),
        readApi<ManagedSubjectRecord[]>('/subjects/', controller.signal),
      ]).then(([classes, subjects]) => {
        if (!controller.signal.aborted) {
          setTeacherClasses(classes);
          setTeacherSubjects(subjects);
        }
      }).catch((error: Error) => {
        if (error.name !== 'AbortError' && !controller.signal.aborted) setProfileError(getSafeErrorMessage(error));
      });
    }
    return () => controller.abort();
  }, [user, activeSection]);

  useEffect(() => {
    if (!user || activeSection !== 'Students' || !['SUPER_ADMIN', 'ADMIN'].includes(user.role)) return;
    const controller = new AbortController();
    setEnrollmentOptionsError('');
    Promise.all([
      readApi<ManagedAcademicYear[]>('/academic-years/', controller.signal),
      readApi<SchoolClassRecord[]>('/classes/', controller.signal),
      readApi<ManagedTerm[]>('/terms/', controller.signal),
    ])
      .then(([years, classes, terms]) => {
        setManagedAcademicYears(years);
        setManagedClasses(classes);
        setManagedTerms(terms);
      })
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setEnrollmentOptionsError(getSafeErrorMessage(error));
      });
    return () => controller.abort();
  }, [user, activeSection]);

  useEffect(() => {
    if (!user || activeSection !== 'Users') return;
    const controller = new AbortController();
    setIsLoadingUsers(true);
    setUserManagementError('');
    fetch(`${apiRoot}/users/`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
      .then((response) => readResponse<ManagedUser[]>(response))
      .then((payload) => setManagedUsers(payload))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setUserManagementError(getSafeErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingUsers(false);
      });
    return () => controller.abort();
  }, [user, activeSection]);

  useEffect(() => {
    if (!user || activeSection !== 'Audit Logs') return;
    const controller = new AbortController();
    const params = new URLSearchParams({ limit: auditLimit });
    if (auditActionFilter) params.set('action', auditActionFilter);
    if (auditModelFilter) params.set('model', auditModelFilter);
    setIsLoadingAuditLogs(true);
    setAuditLogError('');
    fetch(`${apiRoot}/audit-logs/?${params.toString()}`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
      .then((response) => readResponse<AuditLogRecord[]>(response))
      .then((payload) => setAuditLogs(payload))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setAuditLogError(getSafeErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingAuditLogs(false);
      });
    return () => controller.abort();
  }, [user, activeSection, auditActionFilter, auditModelFilter, auditLimit]);

  useEffect(() => {
    if (!user || activeSection !== 'Reports') return;
    const controller = new AbortController();
    setIsLoadingReport(true);
    setReportError('');
    readApi<{ subjects: PerformanceSubject[] }>('/reports/performance/', controller.signal)
      .then((payload) => setReportSubjects(payload.subjects))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setReportError(getSafeErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingReport(false);
      });
    return () => controller.abort();
  }, [user, activeSection]);

  useEffect(() => {
    if (!user || !['Teachers', 'Classes', 'Subjects'].includes(activeSection)) return;
    const controller = new AbortController();
    setIsLoadingDataManagement(true);
    setDataManagementError('');
    const request = activeSection === 'Teachers'
      ? readApi<TeacherRecord[]>('/teachers/', controller.signal).then((rows) => setManagedTeachers(rows))
      : activeSection === 'Classes'
        ? Promise.all([
          readApi<SchoolClassRecord[]>('/classes/', controller.signal),
          readApi<ManagedAcademicYear[]>('/academic-years/', controller.signal),
          readApi<TeacherRecord[]>('/teachers/', controller.signal),
        ]).then(([rows, years, teacherRows]) => {
          setManagedClasses(rows);
          setManagedAcademicYears(years);
          setManagedTeachers(teacherRows);
        })
        : Promise.all([
          readApi<ManagedSubjectRecord[]>('/subjects/', controller.signal),
          readApi<SchoolClassRecord[]>('/classes/', controller.signal),
          readApi<TeacherRecord[]>('/teachers/', controller.signal),
        ]).then(([rows, classRows, teacherRows]) => {
          setManagedSubjects(rows);
          setManagedClasses(classRows);
          setManagedTeachers(teacherRows);
        });
    request
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setDataManagementError(getSafeErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingDataManagement(false);
      });
    return () => controller.abort();
  }, [user, activeSection]);

  useEffect(() => {
    setShowDataManagementForm(false);
    setEditingDataRecordId(null);
    setDataManagementForm(emptyDataManagementForm);
    setDataManagementError('');
    setDataManagementNotice('');
  }, [activeSection]);

  useEffect(() => {
    if (!user || !['SUPER_ADMIN', 'ADMIN'].includes(user.role) || activeSection !== 'Academic Years') return;
    const controller = new AbortController();
    setIsLoadingAcademicYears(true);
    setAcademicYearError('');
    readApi<ManagedAcademicYear[]>('/academic-years/', controller.signal)
      .then((years) => setManagedAcademicYears(years))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setAcademicYearError(getSafeErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingAcademicYears(false);
      });
    return () => controller.abort();
  }, [user, activeSection]);

  useEffect(() => {
    if (!user || !['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) || activeSection !== 'Terms') return;
    const controller = new AbortController();
    setIsLoadingTerms(true);
    setTermError('');
    Promise.all([
      readApi<ManagedTerm[]>('/terms/', controller.signal),
      readApi<ManagedAcademicYear[]>('/academic-years/', controller.signal),
    ])
      .then(([termsPayload, yearsPayload]) => {
        setManagedTerms(termsPayload);
        setManagedAcademicYears(yearsPayload);
      })
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setTermError(getSafeErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingTerms(false);
      });
    return () => controller.abort();
  }, [user, activeSection]);

  useEffect(() => {
    if (!user || !selectedStudent) {
      setStudentResults([]);
      return;
    }
    const controller = new AbortController();
    fetch(`${apiRoot}/results/?student_id=${selectedStudent.id}`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
      .then((response) => readResponse<ResultRecord[]>(response))
      .then((payload) => setStudentResults(payload))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setStudentPageError(getSafeErrorMessage(error));
      });
    return () => controller.abort();
  }, [user, selectedStudent]);

  useEffect(() => {
    if (!user || !selectedStudent || !studentResultYearFilter || !studentResultTermFilter) {
      setStudentAcademicReport(null);
      setStudentReportError('');
      return;
    }
    const controller = new AbortController();
    const query = new URLSearchParams({ academic_year_id: studentResultYearFilter, term_id: studentResultTermFilter });
    setIsLoadingStudentReport(true);
    setStudentReportError('');
    readApi<StudentAcademicReport>(`/students/${selectedStudent.id}/report/?${query.toString()}`, controller.signal)
      .then((payload) => setStudentAcademicReport(payload))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') {
          setStudentAcademicReport(null);
          setStudentReportError(getSafeErrorMessage(error));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingStudentReport(false);
      });
    return () => controller.abort();
  }, [user, selectedStudent, studentResultYearFilter, studentResultTermFilter]);

  useEffect(() => {
    if (!user || activeSection !== 'Results') return;
    const controller = new AbortController();
    const query = resultStatusFilter ? `?status=${encodeURIComponent(resultStatusFilter)}` : '';
    setIsLoadingResults(true);
    setResultError('');
    readApi<ResultRecord[]>(`/results/${query}`, controller.signal)
      .then((rows) => setResultRows(rows))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setResultError(getSafeErrorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoadingResults(false);
      });
    return () => controller.abort();
  }, [user, activeSection, resultStatusFilter]);

  useEffect(() => {
    if (!user || user.role !== 'TEACHER' || activeSection !== 'Results') return;
    if (!bulkContext.subject_id || !bulkContext.academic_year_id || !bulkContext.term_id) {
      setBulkRows([]);
      return;
    }
    const subject = resultSubjects.find((s) => String(s.id) === bulkContext.subject_id);
    const classId = subject?.school_class?.id;
    const enrolled = resultEnrollments.filter(
      (e) =>
        String(e.school_class.id) === String(classId) &&
        String(e.academic_year.id) === bulkContext.academic_year_id &&
        String(e.term.id) === bulkContext.term_id,
    );
    setBulkRows(
      enrolled.map((e) => ({
        student_id: e.student.id,
        name: e.student.full_name,
        admission: e.student.admission_number,
        marks: '',
        remarks: '',
      })),
    );
    setBulkError('');
    setBulkNotice('');
  }, [user, activeSection, bulkContext.subject_id, bulkContext.academic_year_id, bulkContext.term_id, resultEnrollments, resultSubjects]);

  useEffect(() => {
    if (!user || user.role !== 'TEACHER' || activeSection !== 'Results') return;
    const controller = new AbortController();
    setResultOptionsError('');
    Promise.all([
      readApi<AcademicYearOption[]>('/academic-years/', controller.signal),
      readApi<TermOption[]>('/terms/', controller.signal),
      readApi<SubjectOption[]>('/subjects/', controller.signal),
      readApi<EnrollmentOption[]>('/enrollments/', controller.signal),
    ])
      .then(([years, terms, subjects, enrollments]) => {
        setResultYears(years);
        setResultTerms(terms);
        setResultSubjects(subjects);
        setResultEnrollments(enrollments);
      })
      .catch((error: Error) => {
        if (error.name !== 'AbortError') setResultOptionsError(getSafeErrorMessage(error));
      });
    return () => controller.abort();
  }, [user, activeSection]);

  const statCards = useMemo<Array<{ label: string; value: number | string; color: string; section: string; statusFilter?: string }>>(
    () => user?.role === 'TEACHER'
      ? [
        { label: 'My Students', value: dashboard.stats.students, color: 'primary', section: 'Students' },
        { label: 'My Subjects', value: dashboard.stats.subjects, color: 'success', section: 'My Subjects' },
        { label: 'My Classes', value: dashboard.stats.classes, color: 'warning', section: 'My Classes' },
        { label: 'Published This Term', value: dashboard.stats.published_results, color: 'success', section: 'Results', statusFilter: 'PUBLISHED' },
        { label: 'Average Mark', value: dashboard.stats.average_performance === null ? '—' : `${dashboard.stats.average_performance}%`, color: 'success', section: 'Reports' },
      ]
      : user?.role === 'STUDENT'
        ? [
          { label: 'My Profile', value: dashboard.stats.students, color: 'primary', section: 'My Profile' },
          { label: 'Published This Term', value: dashboard.stats.published_results, color: 'info', section: 'My Results', statusFilter: 'PUBLISHED' },
          { label: 'Average Performance', value: dashboard.stats.average_performance === null ? '—' : `${dashboard.stats.average_performance}%`, color: 'success', section: 'My Performance' },
        ]
        : [
          { label: 'Students', value: dashboard.stats.students, color: 'primary', section: 'Students' },
          { label: 'Teachers', value: dashboard.stats.teachers, color: 'success', section: 'Teachers' },
          { label: 'Classes', value: dashboard.stats.classes, color: 'warning', section: 'Classes' },
          { label: 'Pending Review', value: dashboard.result_status.submitted + dashboard.result_status.under_review, color: 'warning', section: 'Results', statusFilter: 'REVIEW_QUEUE' },
          { label: 'Published', value: dashboard.stats.published_results, color: 'success', section: 'Results', statusFilter: 'PUBLISHED' },
          { label: 'Draft Results', value: dashboard.result_status.draft, color: 'info', section: 'Results', statusFilter: 'DRAFT' },
          { label: 'Under Review', value: dashboard.result_status.under_review, color: 'warning', section: 'Results', statusFilter: 'UNDER_REVIEW' },
          { label: 'Average Mark', value: dashboard.stats.average_performance === null ? '—' : `${dashboard.stats.average_performance}%`, color: 'success', section: 'Reports' },
        ],
    [dashboard, user?.role]
  );
  const dashboardQuickActions: { label: string; section: string; statusFilter?: string }[] = user?.role === 'TEACHER'
    ? [
      { label: 'Enter results', section: 'Enter Results' },
      { label: 'Submitted results', section: 'Submitted Results' },
      { label: 'My classes', section: 'My Classes' },
      { label: 'Reports', section: 'Reports' },
    ]
    : user?.role === 'STUDENT'
      ? [
        { label: 'My results', section: 'My Results' },
        { label: 'My performance', section: 'My Performance' },
        { label: 'Result slip', section: 'Result Slip' },
      ]
      : user?.role === 'ACADEMIC_OFFICER'
        ? [
          { label: 'Review queue', section: 'Results', statusFilter: 'REVIEW_QUEUE' },
          { label: 'Approved results', section: 'Results', statusFilter: 'APPROVED' },
          { label: 'Reports', section: 'Reports' },
          { label: 'Audit logs', section: 'Audit Logs' },
        ]
        : [
          { label: 'Students', section: 'Students' },
          { label: 'Teachers', section: 'Teachers' },
          { label: 'Review queue', section: 'Results', statusFilter: 'REVIEW_QUEUE' },
          { label: 'Reports', section: 'Reports' },
          { label: 'Users & access', section: 'Users' },
        ];
  const resultStatusBars = ['draft', 'submitted', 'under_review', 'approved', 'rejected', 'published'].map((status) => ({
    label: status.split('_').map((part) => part[0].toUpperCase() + part.slice(1)).join(' '),
    count: dashboard.result_status[status as keyof DashboardData['result_status']] || 0,
  }));
  const resultStatusMaximum = Math.max(...resultStatusBars.map((item) => item.count), 1);
  const reviewQueueCount = dashboard.result_status.submitted + dashboard.result_status.under_review;
  const visibleResultStatusBars = user?.role === 'STUDENT'
    ? resultStatusBars.filter((item) => item.label === 'Published')
    : resultStatusBars;
  const publishedStudentResults = studentResults.filter((result) =>
    result.status === 'PUBLISHED'
    && (!studentResultYearFilter || String(result.academic_year?.id) === studentResultYearFilter)
    && (!studentResultTermFilter || String(result.term?.id) === studentResultTermFilter),
  );
  const studentResultYears = resultYears;
  const studentResultTerms = resultTerms.filter((term) =>
    !studentResultYearFilter || String(term.academic_year.id) === studentResultYearFilter,
  );
  const studentSubjectPerformance = useMemo(() => {
    const grouped = new Map<string, { name: string; marks: number[] }>();
    publishedStudentResults.forEach((result) => {
      const key = String(result.subject?.id ?? result.subject?.name ?? 'subject');
      const current = grouped.get(key) || { name: result.subject?.name || 'Subject', marks: [] };
      current.marks.push(result.marks);
      grouped.set(key, current);
    });
    return Array.from(grouped.values()).map((subject) => ({
      name: subject.name,
      count: subject.marks.length,
      average: subject.marks.reduce((total, mark) => total + mark, 0) / subject.marks.length,
    })).sort((first, second) => second.average - first.average);
  }, [publishedStudentResults]);
  const studentOverallAverage = publishedStudentResults.length
    ? publishedStudentResults.reduce((total, result) => total + result.marks, 0) / publishedStudentResults.length
    : 0;

  async function handleForgotPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthError('');
    setForgotNotice('');
    setIsSendingReset(true);
    try {
      await readResponse(await fetch(`${apiRoot}/auth/csrf/`, { credentials: 'include' }));
      const response = await fetch(`${apiRoot}/auth/forgot-password/`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ email: forgotEmail }),
      });
      const payload = await readResponse<{ detail: string }>(response);
      setForgotNotice(payload.detail);
      setForgotEmail('');
    } catch (error) {
      setAuthError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to send reset email.');
    } finally {
      setIsSendingReset(false);
    }
  }

  async function handleResetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthError('');
    setResetNotice('');
    setIsResettingPassword(true);
    try {
      await readResponse(await fetch(`${apiRoot}/auth/csrf/`, { credentials: 'include' }));
      const response = await fetch(`${apiRoot}/auth/reset-password/`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ token: resetToken, new_password: newResetPassword }),
      });
      const payload = await readResponse<{ detail: string }>(response);
      setResetNotice(payload.detail);
      setResetDone(true);
      setResetToken('');
      setNewResetPassword('');
    } catch (error) {
      setAuthError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to reset password.');
    } finally {
      setIsResettingPassword(false);
    }
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthError('');
    setIsSubmitting(true);
    try {
      await readResponse(await fetch(`${apiRoot}/auth/csrf/`, { credentials: 'include' }));
      const response = await fetch(`${apiRoot}/auth/login/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ username, password }),
      });
      const payload = await readResponse<{ user: AuthenticatedUser }>(response);
      setUser(payload.user);
      setPassword('');
      setSelectedStudent(null);
      setStudents([]);
      setActiveSection('Dashboard');
    } catch (error) {
      setAuthError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to sign in.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleLogout() {
    setAuthError('');
    setIsSigningOut(true);
    try {
      const response = await fetch(`${apiRoot}/auth/logout/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
      await readResponse(response);
      setUser(null);
      setDashboard(emptyDashboard);
      setUsername('');
      setPassword('');
    } catch (error) {
      setAuthError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to sign out.');
    } finally {
      setIsSigningOut(false);
    }
  }

  async function handleChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordChangeError('');
    setPasswordChangeNotice('');
    setIsChangingPassword(true);
    try {
      await readResponse(await fetch(`${apiRoot}/auth/csrf/`, { credentials: 'include' }));
      const response = await fetch(`${apiRoot}/auth/change-password/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      const payload = await readResponse<{ detail: string }>(response);
      setCurrentPassword('');
      setNewPassword('');
      setPasswordChangeNotice(payload.detail);
    } catch (error) {
      setPasswordChangeError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to update your password.');
    } finally {
      setIsChangingPassword(false);
    }
  }

  function startCreateUser() {
    setEditingUserId(null);
    setUserForm(emptyUserForm);
    setUserManagementError('');
    setUserManagementNotice('');
    setShowUserForm(true);
  }

  function startEditUser(account: ManagedUser) {
    setEditingUserId(account.id);
    setUserForm({
      username: account.username,
      first_name: account.first_name,
      last_name: account.last_name,
      email: account.email,
      role: account.role,
      phone_number: account.phone_number,
      password: '',
    });
    setUserManagementError('');
    setUserManagementNotice('');
    setShowUserForm(true);
  }

  async function refreshManagedUsers() {
    const response = await fetch(`${apiRoot}/users/`, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    });
    setManagedUsers(await readResponse<ManagedUser[]>(response));
  }

  async function handleSaveUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) return;
    setIsSavingUser(true);
    setUserManagementError('');
    setUserManagementNotice('');
    try {
      const payload: Partial<UserForm> = { ...userForm };
      if (editingUserId && !payload.password) delete payload.password;
      const response = await fetch(
        `${apiRoot}/users/${editingUserId ? `${editingUserId}/` : ''}`,
        {
          method: editingUserId ? 'PATCH' : 'POST',
          credentials: 'include',
          headers: {
            Accept: 'application/json',
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify(payload),
        },
      );
      const savedUser = await readResponse<ManagedUser>(response);
      if (savedUser.id === user.id) {
        setUser({
          ...user,
          username: savedUser.username,
          name: [savedUser.first_name, savedUser.last_name].filter(Boolean).join(' ') || savedUser.username,
          role: savedUser.role,
        });
      }
      await refreshManagedUsers();
      setShowUserForm(false);
      setEditingUserId(null);
      setUserForm(emptyUserForm);
      setUserManagementNotice(editingUserId ? 'User account updated.' : 'User account created.');
    } catch (error) {
      setUserManagementError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to save the user account.');
    } finally {
      setIsSavingUser(false);
    }
  }

  async function handleUserStatusChange(account: ManagedUser, activate: boolean) {
    const action = activate ? 'reactivate' : 'disable';
    if (!activate && !window.confirm(`Disable the account for ${account.username}?`)) return;
    setUserManagementError('');
    setUserManagementNotice('');
    try {
      const response = await fetch(`${apiRoot}/users/${account.id}/`, {
        method: activate ? 'PATCH' : 'DELETE',
        credentials: 'include',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        ...(activate ? { body: JSON.stringify({ is_active: true }) } : {}),
      });
      if (activate) await readResponse<ManagedUser>(response);
      else if (!response.ok) await readResponse(response);
      await refreshManagedUsers();
      setUserManagementNotice(`User account ${activate ? 'reactivated' : 'disabled'}.`);
    } catch (error) {
      setUserManagementError(error instanceof Error ? getSafeErrorMessage(error) : `Unable to ${action} the account.`);
    }
  }

  function beginResultEdit(result: ResultRecord) {
    setEditingResultId(result.id);
    setResultForm({
      student_id: String(result.student?.id || ''),
      subject_id: String(result.subject?.id || ''),
      academic_year_id: String(result.academic_year?.id || ''),
      term_id: String(result.term?.id || ''),
      assessment_type: result.assessment_type || 'CAT',
      marks: String(result.marks),
      remarks: result.remarks || '',
    });
    setResultError('');
    setResultNotice('');
  }

  async function refreshResultRows() {
    const query = resultStatusFilter ? `?status=${encodeURIComponent(resultStatusFilter)}` : '';
    const response = await fetch(`${apiRoot}/results/${query}`, { credentials: 'include', headers: { Accept: 'application/json' } });
    setResultRows(await readResponse<ResultRecord[]>(response));
  }

  async function handleBulkSave(submit: boolean) {
    setBulkError('');
    setBulkNotice('');
    setIsSavingBulk(true);
    try {
      const response = await fetch(`${apiRoot}/results/bulk/`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({
          subject_id: Number(bulkContext.subject_id),
          academic_year_id: Number(bulkContext.academic_year_id),
          term_id: Number(bulkContext.term_id),
          assessment_type: bulkContext.assessment_type,
          submit,
          rows: bulkRows.map((r) => ({ student_id: r.student_id, marks: r.marks, remarks: r.remarks })),
        }),
      });
      const payload = await readResponse<{ created: number; updated: number }>(response);
      await refreshResultRows();
      setBulkNotice(`Saved: ${payload.created} new, ${payload.updated} updated.${submit ? ' All submitted for review.' : ' Saved as drafts.'}`);
    } catch (error) {
      setBulkError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to save results.');
    } finally {
      setIsSavingBulk(false);
    }
  }

  async function handleBulkApprove(action: 'approve' | 'return' | 'publish') {
    if (!bulkApprovalIds.size) return;
    setBulkApprovalError('');
    setBulkApprovalNotice('');
    setIsBulkApproving(true);
    try {
      const response = await fetch(`${apiRoot}/results/bulk-approve/`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ result_ids: Array.from(bulkApprovalIds), action, comments: bulkApprovalComments }),
      });
      const payload = await readResponse<{ processed: number; skipped: number }>(response);
      await refreshResultRows();
      setBulkApprovalIds(new Set());
      setBulkApprovalComments('');
      setBulkApprovalNotice(`${payload.processed} result(s) ${action}d.${payload.skipped ? ` ${payload.skipped} skipped.` : ''}`);
    } catch (error) {
      setBulkApprovalError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to process bulk action.');
    } finally {
      setIsBulkApproving(false);
    }
  }

  async function handleBulkEnroll(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!bulkEnrollIds.size) { setBulkEnrollError('Select at least one student.'); return; }
    setBulkEnrollError('');
    setBulkEnrollNotice('');
    setIsSavingBulkEnroll(true);
    try {
      const response = await fetch(`${apiRoot}/enrollments/bulk/`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({
          student_ids: Array.from(bulkEnrollIds),
          school_class_id: Number(bulkEnrollContext.school_class_id),
          academic_year_id: Number(bulkEnrollContext.academic_year_id),
          term_id: Number(bulkEnrollContext.term_id),
        }),
      });
      const payload = await readResponse<{ created: number; skipped: number }>(response);
      setBulkEnrollIds(new Set());
      setBulkEnrollContext({ academic_year_id: '', school_class_id: '', term_id: '' });
      setShowBulkEnrollForm(false);
      setBulkEnrollNotice(`${payload.created} student(s) enrolled.${payload.skipped ? ` ${payload.skipped} already enrolled.` : ''}`);
      const params = new URLSearchParams();
      if (studentSearch.trim()) params.set('q', studentSearch.trim());
      if (studentClassFilter) params.set('class_id', studentClassFilter);
      setStudents(await readApi<StudentRecord[]>(`/students/?${params.toString()}`));
    } catch (error) {
      setBulkEnrollError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to enroll students.');
    } finally {
      setIsSavingBulkEnroll(false);
    }
  }

  function parseCsvRows(csv: string): Record<string, string>[] {
    const lines = csv.trim().split('\n').filter(Boolean);
    if (lines.length < 2) return [];
    const headers = lines[0].split(',').map((h) => h.trim().replace(/^"|"$/g, ''));
    return lines.slice(1).map((line) => {
      const values = line.split(',').map((v) => v.trim().replace(/^"|"$/g, ''));
      return Object.fromEntries(headers.map((h, i) => [h, values[i] || '']));
    });
  }

  async function handleBulkImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBulkImportError('');
    setBulkImportNotice('');
    setIsBulkImporting(true);
    try {
      const rows = parseCsvRows(bulkImportCsv);
      if (!rows.length) { setBulkImportError('Paste valid CSV data with a header row.'); setIsBulkImporting(false); return; }
      const response = await fetch(`${apiRoot}/users/bulk-import/`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ role: bulkImportRole, rows }),
      });
      const payload = await readResponse<{ created: number }>(response);
      setBulkImportCsv('');
      setShowBulkImport(false);
      setBulkImportNotice(`${payload.created} ${bulkImportRole.toLowerCase()} account(s) created.`);
      if (bulkImportRole === 'STUDENT') setStudents(await readApi<StudentRecord[]>('/students/'));
      else setManagedTeachers(await readApi<TeacherRecord[]>('/teachers/'));
    } catch (error) {
      setBulkImportError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to import accounts.');
    } finally {
      setIsBulkImporting(false);
    }
  }

  async function handleSaveResult(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!user) return;
    setIsSavingResult(true);
    setResultError('');
    setResultNotice('');
    try {
      const payload = editingResultId
        ? { marks: resultForm.marks, remarks: resultForm.remarks }
        : {
          student_id: Number(resultForm.student_id),
          subject_id: Number(resultForm.subject_id),
          academic_year_id: Number(resultForm.academic_year_id),
          term_id: Number(resultForm.term_id),
          assessment_type: resultForm.assessment_type,
          marks: resultForm.marks,
          remarks: resultForm.remarks,
          status: 'DRAFT',
        };
      const response = await fetch(`${apiRoot}/results/${editingResultId ? `${editingResultId}/` : ''}`, {
        method: editingResultId ? 'PATCH' : 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify(payload),
      });
      await readResponse<ResultRecord>(response);
      await refreshResultRows();
      setEditingResultId(null);
      setResultForm(emptyResultForm);
      setResultNotice(editingResultId ? 'Draft updated. Submit it when it is ready for review.' : 'Draft saved. Submit it when it is ready for review.');
    } catch (error) {
      setResultError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to save this result.');
    } finally {
      setIsSavingResult(false);
    }
  }

  async function handleResultStatusChange(result: ResultRecord, nextStatus: string) {
    setResultError('');
    setResultNotice('');
    try {
      const response = await fetch(`${apiRoot}/results/${result.id}/`, {
        method: 'PATCH',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({
          status: nextStatus,
          ...(['UNDER_REVIEW', 'APPROVED', 'RETURNED', 'PUBLISHED'].includes(nextStatus)
            ? { comments: reviewComments[result.id] || '' } : {}),
        }),
      });
      await readResponse<ResultRecord>(response);
      await refreshResultRows();
      setReviewComments((current) => ({ ...current, [result.id]: '' }));
      setResultNotice(`Result ${nextStatus.toLowerCase().replace('_', ' ')}.`);
    } catch (error) {
      setResultError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to update the result workflow.');
    }
  }

  function startCreateAcademicYear() {
    setEditingAcademicYearId(null);
    setShowAcademicYearForm(true);
    setAcademicYearForm(emptyAcademicYearForm);
    setAcademicYearError('');
    setAcademicYearNotice('');
  }

  function startEditAcademicYear(year: ManagedAcademicYear) {
    setEditingAcademicYearId(year.id);
    setShowAcademicYearForm(true);
    setAcademicYearForm({
      name: year.name,
      start_date: year.start_date,
      end_date: year.end_date,
      is_active: year.is_active,
    });
    setAcademicYearError('');
    setAcademicYearNotice('');
  }

  async function handleSaveAcademicYear(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingAcademicYear(true);
    setAcademicYearError('');
    setAcademicYearNotice('');
    try {
      const response = await fetch(`${apiRoot}/academic-years/${editingAcademicYearId ? `${editingAcademicYearId}/` : ''}`, {
        method: editingAcademicYearId ? 'PATCH' : 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify(academicYearForm),
      });
      await readResponse<ManagedAcademicYear>(response);
      setManagedAcademicYears(await readApi<ManagedAcademicYear[]>('/academic-years/'));
      setEditingAcademicYearId(null);
      setShowAcademicYearForm(false);
      setAcademicYearForm(emptyAcademicYearForm);
      setAcademicYearNotice(editingAcademicYearId ? 'Academic year updated.' : 'Academic year created.');
    } catch (error) {
      setAcademicYearError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to save the academic year.');
    } finally {
      setIsSavingAcademicYear(false);
    }
  }

  function startCreateTerm() {
    setEditingTermId(null);
    setShowTermForm(true);
    setTermForm(emptyTermForm);
    setTermError('');
    setTermNotice('');
  }

  function startEditTerm(term: ManagedTerm) {
    setEditingTermId(term.id);
    setShowTermForm(true);
    setTermForm({
      academic_year_id: String(term.academic_year.id),
      name: term.name,
      start_date: term.start_date,
      end_date: term.end_date,
      is_active: term.is_active,
    });
    setTermError('');
    setTermNotice('');
  }

  async function handleSaveTerm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingTerm(true);
    setTermError('');
    setTermNotice('');
    try {
      const response = await fetch(`${apiRoot}/terms/${editingTermId ? `${editingTermId}/` : ''}`, {
        method: editingTermId ? 'PATCH' : 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify(termForm),
      });
      await readResponse<ManagedTerm>(response);
      const termsPayload = await readApi<ManagedTerm[]>('/terms/');
      setManagedTerms(termsPayload);
      setEditingTermId(null);
      setShowTermForm(false);
      setTermForm(emptyTermForm);
      setTermNotice(editingTermId ? 'Term updated.' : 'Term created.');
    } catch (error) {
      setTermError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to save this term.');
    } finally {
      setIsSavingTerm(false);
    }
  }

  function startDataManagementCreate() {
    setEditingDataRecordId(null);
    setDataManagementForm(emptyDataManagementForm);
    setDataManagementError('');
    setDataManagementNotice('');
    setShowDataManagementForm(true);
  }

  function startDataManagementEdit(record: StudentRecord | TeacherRecord | SchoolClassRecord | ManagedSubjectRecord) {
    setEditingDataRecordId(record.id);
    setDataManagementError('');
    setDataManagementNotice('');
    setShowDataManagementForm(true);
    if (activeSection === 'Students') {
      const student = record as StudentRecord;
      setDataManagementForm({
        ...emptyDataManagementForm,
        first_name: student.user?.first_name || '', last_name: student.user?.last_name || '',
        email: student.user?.email || '', phone_number: student.user?.phone_number || '',
        admission_number: student.admission_number, date_of_birth: student.date_of_birth || '',
        gender: student.gender, current_class: student.current_class,
      });
    } else if (activeSection === 'Teachers') {
      const teacher = record as TeacherRecord;
      setDataManagementForm({
        ...emptyDataManagementForm,
        first_name: teacher.user.first_name, last_name: teacher.user.last_name, email: teacher.user.email,
        phone_number: teacher.phone_number, employee_id: teacher.employee_id,
        department: teacher.department, qualification: teacher.qualification,
      });
    } else if (activeSection === 'Classes') {
      const schoolClass = record as SchoolClassRecord;
      setDataManagementForm({
        ...emptyDataManagementForm,
        name: schoolClass.name, section: schoolClass.section,
        academic_year_id: String(schoolClass.academic_year.id), teacher_id: schoolClass.teacher_id ? String(schoolClass.teacher_id) : '',
        is_active: schoolClass.is_active,
      });
    } else {
      const subject = record as ManagedSubjectRecord;
      setDataManagementForm({
        ...emptyDataManagementForm,
        code: subject.code, name: subject.name, school_class_id: String(subject.school_class.id),
        teacher_id: subject.teacher_id ? String(subject.teacher_id) : '', description: subject.description,
      });
    }
  }

  async function refreshDataManagementList(section: string) {
    if (section === 'Students') setStudents(await readApi<StudentRecord[]>('/students/'));
    else if (section === 'Teachers') setManagedTeachers(await readApi<TeacherRecord[]>('/teachers/'));
    else if (section === 'Classes') setManagedClasses(await readApi<SchoolClassRecord[]>('/classes/'));
    else if (section === 'Subjects') setManagedSubjects(await readApi<ManagedSubjectRecord[]>('/subjects/'));
  }

  async function handleSaveDataManagementRecord(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingDataManagement(true);
    setDataManagementError('');
    setDataManagementNotice('');
    try {
      let endpoint = '';
      let payload: Record<string, unknown> = {};
      if (activeSection === 'Students') {
        endpoint = `/students/${editingDataRecordId ? `${editingDataRecordId}/` : ''}`;
        const { first_name, last_name, email, phone_number, admission_number, date_of_birth, gender, current_class } = dataManagementForm;
        payload = { first_name, last_name, email, phone_number, admission_number, date_of_birth: date_of_birth || null, gender, current_class };
        if (!editingDataRecordId) Object.assign(payload, { username: dataManagementForm.username, password: dataManagementForm.password });
      } else if (activeSection === 'Teachers') {
        endpoint = `/teachers/${editingDataRecordId ? `${editingDataRecordId}/` : ''}`;
        const { first_name, last_name, email, employee_id, department, qualification, phone_number } = dataManagementForm;
        payload = { first_name, last_name, email, employee_id, department, qualification, phone_number };
        if (!editingDataRecordId) Object.assign(payload, { username: dataManagementForm.username, password: dataManagementForm.password });
        else if (dataManagementForm.password) Object.assign(payload, { password: dataManagementForm.password });
      } else if (activeSection === 'Classes') {
        endpoint = `/classes/${editingDataRecordId ? `${editingDataRecordId}/` : ''}`;
        payload = { name: dataManagementForm.name, section: dataManagementForm.section, academic_year_id: Number(dataManagementForm.academic_year_id), teacher_id: dataManagementForm.teacher_id ? Number(dataManagementForm.teacher_id) : null, is_active: dataManagementForm.is_active };
      } else {
        endpoint = `/subjects/${editingDataRecordId ? `${editingDataRecordId}/` : ''}`;
        payload = { code: dataManagementForm.code, name: dataManagementForm.name, school_class_id: Number(dataManagementForm.school_class_id), teacher_id: dataManagementForm.teacher_id ? Number(dataManagementForm.teacher_id) : null, description: dataManagementForm.description };
      }
      const response = await fetch(`${apiRoot}${endpoint}`, {
        method: editingDataRecordId ? 'PATCH' : 'POST', credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify(payload),
      });
      await readResponse<unknown>(response);
      await refreshDataManagementList(activeSection);
      setShowDataManagementForm(false);
      setEditingDataRecordId(null);
      setDataManagementForm(emptyDataManagementForm);
      setDataManagementNotice(`${activeSection === 'Classes' ? 'Class' : activeSection === 'Subjects' ? 'Subject' : activeSection === 'Teachers' ? 'Teacher' : 'Student'} ${editingDataRecordId ? 'updated' : 'created'}.`);
    } catch (error) {
      setDataManagementError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to save this record.');
    } finally {
      setIsSavingDataManagement(false);
    }
  }

  function startStudentEnrollment(student: StudentRecord) {
    setEnrollmentForm({ ...emptyEnrollmentForm, student_id: String(student.id) });
    setEnrollmentError('');
    setShowEnrollmentForm(true);
  }

  async function handleCreateEnrollment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSavingEnrollment(true);
    setEnrollmentError('');
    try {
      const response = await fetch(`${apiRoot}/enrollments/`, {
        method: 'POST', credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({
          student_id: Number(enrollmentForm.student_id),
          school_class_id: Number(enrollmentForm.school_class_id),
          academic_year_id: Number(enrollmentForm.academic_year_id),
          term_id: Number(enrollmentForm.term_id),
        }),
      });
      await readResponse<unknown>(response);
      setShowEnrollmentForm(false);
      setEnrollmentForm(emptyEnrollmentForm);
      setDataManagementNotice('Student enrolled in the selected class and term.');
      const params = new URLSearchParams();
      if (studentSearch.trim()) params.set('q', studentSearch.trim());
      if (studentClassFilter) params.set('class_id', studentClassFilter);
      setStudents(await readApi<StudentRecord[]>(`/students/?${params.toString()}`));
    } catch (error) {
      setEnrollmentError(error instanceof Error ? getSafeErrorMessage(error) : 'Unable to enroll this student.');
    } finally {
      setIsSavingEnrollment(false);
    }
  }

  function openClassRoster(schoolClass: SchoolClassRecord) {
    setStudentSearch('');
    setStudentClassFilter(String(schoolClass.id));
    setSelectedStudent(null);
    setActiveSection('Students');
  }

  function exportPerformanceReport() {
    const csvValue = (value: string | number) => `"${String(value).replace(/"/g, '""')}"`;
    const rows = [
      ['Subject code', 'Subject', 'Average marks (%)', 'Students with results'],
      ...reportSubjects.map((subject) => [subject.code, subject.name, subject.average_marks, subject.total_students]),
    ];
    const csv = rows.map((row) => row.map(csvValue).join(',')).join('\r\n');
    const file = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(file);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'srms-subject-performance.csv';
    link.click();
    URL.revokeObjectURL(url);
  }

  if (isCheckingSession) {
    return <main className="session-loading" aria-live="polite">Checking your secure session...</main>;
  }

  if (!user) {
    return (
      <main className="login-page">
        <section className="login-intro">
          <div className="intro-copy">
            <span className="intro-kicker">STUDENT RESULTS MANAGEMENT SYSTEM</span>
            <h1>Manage results.<br />Empower students.<br />Build better schools.</h1>
            <p>A secure platform for managing student results, assessments, academic records and performance.</p>
            <div className="login-features">
              <span className="login-features-title">STUDENT RESULTS</span>
              <ul>
                {['Continuous assessment', 'Examination results', 'Grade management', 'Report cards', 'Academic performance'].map((feature) => <li key={feature}><span aria-hidden="true">✓</span>{feature}</li>)}
              </ul>
            </div>
          </div>
          <div className="intro-footer"><span className="secure-dot" /> Secure access · Protected school records</div>
          <div className="intro-orbit orbit-one" />
          <div className="intro-orbit orbit-two" />
        </section>

        <section className="login-panel">
          {resetToken ? (
            <form className="login-card" onSubmit={handleResetPassword}>
              <span className="eyebrow">PASSWORD RESET</span>
              <h2>Set new password</h2>
              <p className="login-subtitle">Enter a new password for your account.</p>
              {resetDone ? (
                <>
                  <p className="user-management-notice" role="status">{resetNotice}</p>
                  <button className="sign-in-btn" type="button" onClick={() => { setResetDone(false); setResetNotice(''); setAuthError(''); }}>
                    Back to sign in <span aria-hidden="true">→</span>
                  </button>
                </>
              ) : (
                <>
                  <label className="form-field">
                    <span>New password</span>
                    <div className="login-password-control">
                      <input
                        autoComplete="new-password"
                        required
                        minLength={8}
                        type={showLoginPassword ? 'text' : 'password'}
                        value={newResetPassword}
                        onChange={(event) => setNewResetPassword(event.target.value)}
                        placeholder="At least 8 characters"
                      />
                      <button className="password-visibility-btn" type="button" onClick={() => setShowLoginPassword((v) => !v)} aria-label={showLoginPassword ? 'Hide password' : 'Show password'} aria-pressed={showLoginPassword}>
                        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                          {showLoginPassword ? <><path d="M3 3l18 18" /><path d="M10.6 10.6a2 2 0 002.8 2.8" /><path d="M9.9 5.2A10.8 10.8 0 0112 5c5 0 8.3 4.4 9 6-.3.8-1.3 2.2-2.8 3.5M6.2 6.2C4.4 7.3 3.3 9.1 3 11c.7 1.6 4 6 9 6 1 0 1.9-.2 2.8-.5" /></> : <><path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6z" /><circle cx="12" cy="12" r="2.5" /></>}
                        </svg>
                      </button>
                    </div>
                  </label>
                  {authError ? <p className="form-error" role="alert">{authError}</p> : null}
                  <button className="sign-in-btn" type="submit" disabled={isResettingPassword}>
                    {isResettingPassword ? 'Resetting...' : 'Reset password'} <span aria-hidden="true">→</span>
                  </button>
                </>
              )}
            </form>
          ) : forgotPasswordView ? (
            <form className="login-card" onSubmit={handleForgotPassword}>
              <span className="eyebrow">ACCOUNT RECOVERY</span>
              <h2>Forgot password?</h2>
              <p className="login-subtitle">Enter your registered email address and we will send you a reset link.</p>
              {forgotNotice ? (
                <>
                  <p className="user-management-notice" role="status">{forgotNotice}</p>
                  <button className="sign-in-btn" type="button" onClick={() => { setForgotPasswordView(false); setForgotNotice(''); setAuthError(''); }}>
                    Back to sign in <span aria-hidden="true">→</span>
                  </button>
                </>
              ) : (
                <>
                  <label className="form-field">
                    <span>Email address</span>
                    <input
                      autoComplete="email"
                      required
                      type="email"
                      value={forgotEmail}
                      onChange={(event) => setForgotEmail(event.target.value)}
                      placeholder="Enter your registered email"
                    />
                  </label>
                  {authError ? <p className="form-error" role="alert">{authError}</p> : null}
                  <button className="sign-in-btn" type="submit" disabled={isSendingReset}>
                    {isSendingReset ? 'Sending...' : 'Send reset link'} <span aria-hidden="true">→</span>
                  </button>
                  <p className="login-note">
                    <button type="button" className="text-btn" onClick={() => { setForgotPasswordView(false); setAuthError(''); }}>← Back to sign in</button>
                  </p>
                </>
              )}
            </form>
          ) : (
            <form className="login-card" onSubmit={handleLogin}>
              <span className="eyebrow">WELCOME BACK</span>
              <h2>Welcome back</h2>
              <p className="login-subtitle">Sign in to your school account to continue.</p>
              <label className="form-field">
                <span>Username</span>
                <input
                  autoComplete="username"
                  name="username"
                  required
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="Enter your username"
                />
              </label>
              <label className="form-field">
                <span>Password</span>
                <div className="login-password-control">
                  <input
                    autoComplete="current-password"
                    name="password"
                    required
                    type={showLoginPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Enter your password"
                  />
                  <button className="password-visibility-btn" type="button" onClick={() => setShowLoginPassword((visible) => !visible)} aria-label={showLoginPassword ? 'Hide password' : 'Show password'} aria-pressed={showLoginPassword}>
                    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      {showLoginPassword ? <><path d="M3 3l18 18" /><path d="M10.6 10.6a2 2 0 002.8 2.8" /><path d="M9.9 5.2A10.8 10.8 0 0112 5c5 0 8.3 4.4 9 6-.3.8-1.3 2.2-2.8 3.5M6.2 6.2C4.4 7.3 3.3 9.1 3 11c.7 1.6 4 6 9 6 1 0 1.9-.2 2.8-.5" /></> : <><path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6z" /><circle cx="12" cy="12" r="2.5" /></>}
                    </svg>
                  </button>
                </div>
              </label>
              <p className="login-note" style={{ textAlign: 'right', marginBottom: 0 }}>
                <button type="button" className="text-btn" onClick={() => { setForgotPasswordView(true); setAuthError(''); }}>Forgot password?</button>
              </p>
              {authError ? <p className="form-error" role="alert">{authError}</p> : null}
              <button className="sign-in-btn" type="submit" disabled={isSubmitting}>
                {isSubmitting ? 'Signing in...' : 'Sign in securely'} <span aria-hidden="true">→</span>
              </button>
            </form>
          )}
        </section>
      </main>
    );
  }

  const roleLabel = roleOptions.find((option) => option.role === user.role)?.label || 'User';
  const hasDashboard = true;
  const isAdminWorkspace = ['SUPER_ADMIN', 'ADMIN'].includes(user.role);
  const adminStandaloneItems = ['Dashboard', 'Results', 'Reports', 'Users', 'Audit Logs'];
  const setNavigationSection = (item: string) => {
    if (studentWorkspaceItems.includes(item)) setStudentWorkspaceView(item);
    if (item === 'Submitted Results') { setTeacherResultsView(item); setResultStatusFilter('SUBMITTED'); }
    if (item === 'Enter Results') { setTeacherResultsView(item); setResultStatusFilter(''); }
    if (item === 'Students') setStudentClassFilter('');
    setActiveSection(
      ['My Profile', 'My Results', 'My Performance', 'Result Slip'].includes(item) ? 'Students'
        : ['Enter Results', 'Submitted Results'].includes(item) ? 'Results' : item,
    );
  };
  const isNavigationItemActive = (item: string) => {
    if (activeSection === 'Students' && studentWorkspaceItems.includes(item)) return studentWorkspaceView === item;
    if (activeSection === 'Results' && user.role === 'TEACHER' && ['Enter Results', 'Submitted Results'].includes(item)) return teacherResultsView === item;
    return activeSection === item;
  };
  const studentResultsTable = (
    <table><thead><tr><th>Subject</th><th>Academic year</th><th>Term</th><th>Assessment</th><th>Marks</th><th>Grade</th></tr></thead>
      <tbody>{publishedStudentResults.map((result) => <tr key={result.id}><td>{result.subject?.name || 'Subject'}</td><td>{result.academic_year?.name || '—'}</td><td>{result.term?.name || '—'}</td><td>{result.assessment_type || '—'}</td><td>{result.marks}</td><td>{result.grade}</td></tr>)}
        {!publishedStudentResults.length ? <tr><td colSpan={6} className="empty-table">No published results are available for this selection.</td></tr> : null}
      </tbody>
    </table>
  );

  return (
    <div className="app-shell">
      <aside className={`sidebar ${user.role === 'STUDENT' ? 'sidebar-student' : ''}`}>
        <div className="brand-block">
          <span className="brand-mark"><SchoolLogo /></span>
          <span><h1>SRMS</h1><p>Academic Portal</p><small>Student Results Management</small></span>
        </div>
        <nav className="nav-menu" aria-label="Role access">
          <span className="nav-section-label">YOUR WORKSPACE</span>
          {isAdminWorkspace ? (
            <>
              <button type="button" onClick={() => setNavigationSection('Dashboard')} className={`nav-item ${activeSection === 'Dashboard' ? 'active' : ''}`} aria-current={activeSection === 'Dashboard' ? 'page' : undefined}>
                <SidebarIcon name="Dashboard" />Dashboard
              </button>
              <details className="nav-group" open>
                <summary className="nav-group-toggle"><SidebarIcon name="Data Management" />Data Management<span className="nav-chevron" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="m4 6 4 4 4-4" /></svg></span></summary>
                <div className="nav-group-items">
                  {['Students', 'Teachers', 'Classes', 'Subjects'].map((item) => (
                    <button key={item} type="button" onClick={() => setNavigationSection(item)} className={`nav-item nav-subitem ${isNavigationItemActive(item) ? 'active' : ''}`} aria-current={activeSection === item ? 'page' : undefined}>
                      <SidebarIcon name={item} />{item}
                    </button>
                  ))}
                </div>
              </details>
              <details className="nav-group" open>
                <summary className="nav-group-toggle"><SidebarIcon name="Academic Settings" />Academic Settings<span className="nav-chevron" aria-hidden="true"><svg viewBox="0 0 16 16"><path d="m4 6 4 4 4-4" /></svg></span></summary>
                <div className="nav-group-items">
                  {['Academic Years', 'Terms'].map((item) => (
                    <button key={item} type="button" onClick={() => setNavigationSection(item)} className={`nav-item nav-subitem ${isNavigationItemActive(item) ? 'active' : ''}`} aria-current={activeSection === item ? 'page' : undefined}>
                      <SidebarIcon name={item} />{item}
                    </button>
                  ))}
                </div>
              </details>
              {adminStandaloneItems.filter((item) => item !== 'Dashboard').map((item) => (
                <button key={item} type="button" onClick={() => setNavigationSection(item)} className={`nav-item ${isNavigationItemActive(item) ? 'active' : ''}`} aria-current={activeSection === item ? 'page' : undefined}>
                  <SidebarIcon name={item === 'Users' ? 'Users & Access' : item} />{item === 'Users' ? 'Users & Access' : item}
                </button>
              ))}
            </>
          ) : roleAccess[user.role].map((item, index) => (
            <button key={item} type="button" onClick={() => setNavigationSection(item)} className={`nav-item ${isNavigationItemActive(item) || (activeSection === 'Dashboard' && index === 0) ? 'active' : ''}`} aria-current={isNavigationItemActive(item) || (activeSection === 'Dashboard' && index === 0) ? 'page' : undefined}>
              <SidebarIcon name={item} />{item}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <span className="eyebrow">{roleLabel.toUpperCase()} WORKSPACE</span>
            <h2>{activeSection === 'Dashboard' ? 'Student Results Management System' : activeSection === 'Profile' ? 'My Profile' : activeSection === 'Account Settings' ? 'Account Settings' : activeSection === 'Students' && user.role === 'STUDENT' ? studentWorkspaceView : activeSection === 'Students' ? 'Student directory' : activeSection === 'My Classes' ? 'My classes' : activeSection === 'My Subjects' ? 'My subjects' : activeSection === 'Teachers' ? 'Teacher directory' : activeSection === 'Classes' ? 'Class management' : activeSection === 'Subjects' ? 'Subject management' : activeSection === 'Users' ? 'User management' : activeSection === 'Audit Logs' ? 'Audit logs' : activeSection === 'Academic Years' ? 'Academic year settings' : activeSection === 'Terms' ? 'Term settings' : activeSection === 'Results' ? 'Results workflow' : `Welcome, ${user.name}`}</h2>
            {activeSection === 'Dashboard' ? <p className="dashboard-context">{dashboard.academic_context.academic_year && dashboard.academic_context.term ? `${dashboard.academic_context.academic_year} · ${dashboard.academic_context.term}` : 'No active academic year and term'}</p> : null}
          </div>
          <div className="topbar-account">
            <details className="profile-menu">
              <summary className="profile-menu-trigger" aria-label={`Open ${user.name}'s profile menu`}>
                <span className="profile-avatar" aria-hidden="true">{user.name.trim().charAt(0).toUpperCase()}</span>
                <span className="profile-trigger-copy"><strong>{user.name}</strong><small>{roleLabel}</small></span>
                <span className="profile-chevron" aria-hidden="true">⌄</span>
              </summary>
              <div className="profile-menu-popover">
                <div className="profile-menu-heading"><span className="profile-avatar" aria-hidden="true">{user.name.trim().charAt(0).toUpperCase()}</span><span><strong>{user.name}</strong><small>{roleLabel}</small></span></div>
                <div className="profile-menu-divider" />
                <button type="button" onClick={(event) => { if (user.role === 'STUDENT') setNavigationSection('My Profile'); else setActiveSection('Profile'); event.currentTarget.closest('details')?.removeAttribute('open'); }}>My Profile</button>
                <button type="button" onClick={(event) => { setActiveSection('Account Settings'); event.currentTarget.closest('details')?.removeAttribute('open'); }}>Account Settings</button>
                <button type="button" onClick={(event) => { setActiveSection('Account Settings'); setPasswordChangeNotice(''); setPasswordChangeError(''); event.currentTarget.closest('details')?.removeAttribute('open'); }}>Change Password</button>
                <div className="profile-menu-divider" />
                <button type="button" className="profile-menu-signout" onClick={handleLogout} disabled={isSigningOut}>
                  {isSigningOut ? 'Signing out...' : 'Sign Out'}
                </button>
              </div>
            </details>
          </div>
        </header>

        {activeSection === 'Profile' ? (
          <section className="panel profile-page">
            <div className="panel-header"><div><span className="eyebrow">Personal workspace</span><h3>{user.name}</h3></div><span className="account-status active">{roleLabel}</span></div>
            {profileError ? <p className="dashboard-error" role="alert">{profileError}</p> : null}
            {isLoadingProfile ? <p className="empty-note">Loading your profile...</p> : null}
            {user.role === 'TEACHER' && teacherProfile ? <>
              <div className="profile-section"><h4>Personal and account information</h4><dl className="profile-details-grid">
                <div><dt>Full name</dt><dd>{teacherProfile.full_name || user.name}</dd></div><div><dt>Teacher ID</dt><dd>{teacherProfile.employee_id}</dd></div>
                <div><dt>Username</dt><dd>{teacherProfile.account.username}</dd></div><div><dt>Email</dt><dd>{teacherProfile.account.email || 'Not provided'}</dd></div>
                <div><dt>Phone</dt><dd>{teacherProfile.phone_number || teacherProfile.user.phone_number || 'Not provided'}</dd></div><div><dt>Role</dt><dd>Teacher</dd></div>
                <div><dt>Account status</dt><dd>{teacherProfile.account.is_active ? 'Active' : 'Inactive'}</dd></div><div><dt>Date joined</dt><dd>{teacherProfile.account.date_joined ? new Date(teacherProfile.account.date_joined).toLocaleDateString() : 'Not available'}</dd></div>
                <div><dt>Last login</dt><dd>{teacherProfile.account.last_login ? new Date(teacherProfile.account.last_login).toLocaleString() : 'Not available'}</dd></div>
              </dl></div>
              <div className="profile-section"><h4>Professional information</h4><dl className="profile-details-grid">
                <div><dt>Department</dt><dd>{teacherProfile.department || 'Not provided'}</dd></div><div><dt>Qualification</dt><dd>{teacherProfile.qualification || 'Not provided'}</dd></div>
                <div className="profile-wide"><dt>Subjects taught</dt><dd>{teacherSubjects.length ? teacherSubjects.map((subject) => `${subject.name} (${subject.school_class.name})`).join(', ') : 'No subjects assigned'}</dd></div>
                <div className="profile-wide"><dt>Classes assigned</dt><dd>{teacherClasses.length ? teacherClasses.map((schoolClass) => `${schoolClass.name}${schoolClass.section ? ` ${schoolClass.section}` : ''} · ${schoolClass.academic_year.name}`).join(', ') : 'No classes assigned'}</dd></div>
                <div><dt>Current academic year</dt><dd>{dashboard.academic_context.academic_year || 'Not set'}</dd></div>
              </dl></div>
            </> : user.role !== 'TEACHER' && accountProfile ? <div className="profile-section"><h4>Account information</h4><dl className="profile-details-grid"><div><dt>Name</dt><dd>{accountProfile.name}</dd></div><div><dt>Username</dt><dd>{accountProfile.username}</dd></div><div><dt>Email</dt><dd>{accountProfile.email || 'Not provided'}</dd></div><div><dt>Role</dt><dd>{roleLabel}</dd></div></dl></div> : null}
          </section>
        ) : null}

        {activeSection === 'Account Settings' ? (
          <section className="panel profile-page account-settings-page">
            <div className="panel-header"><div><span className="eyebrow">Security</span><h3>Account settings</h3></div></div>
            {profileError ? <p className="dashboard-error" role="alert">{profileError}</p> : null}
            {isLoadingProfile ? <p className="empty-note">Loading account details...</p> : null}
            {accountProfile || teacherProfile ? <div className="account-summary"><span>Signed in as</span><strong>{teacherProfile?.account.username || accountProfile?.username || user.username}</strong><span>{teacherProfile?.account.email || accountProfile?.email || 'No email address added'}</span></div> : null}
            <form className="password-change-form" onSubmit={handleChangePassword}>
              <h4>Change password</h4>
              {passwordChangeError ? <p className="dashboard-error" role="alert">{passwordChangeError}</p> : null}
              {passwordChangeNotice ? <p className="user-management-notice" role="status">{passwordChangeNotice}</p> : null}
              <label className="form-field"><span>Current password</span><input type="password" autoComplete="current-password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
              <label className="form-field"><span>New password</span><input type="password" autoComplete="new-password" required minLength={8} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label>
              <button className="primary-btn" type="submit" disabled={isChangingPassword}>{isChangingPassword ? 'Updating...' : 'Update password'}</button>
            </form>
          </section>
        ) : null}

        {activeSection === 'Terms' && ['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) ? (
          <section className="panel academic-year-panel">
            <div className="panel-header">
              <div><span className="eyebrow">School setup</span><h3>Terms</h3></div>
              <button className="primary-btn" type="button" onClick={startCreateTerm}>Add term</button>
            </div>
            <p className="empty-note academic-year-description">Set term dates within their academic year. Terms with existing records stay attached to their original year.</p>
            {termError ? <p className="dashboard-error" role="alert">{termError}</p> : null}
            {termNotice ? <p className="user-management-notice" role="status">{termNotice}</p> : null}
            {showTermForm || (!managedTerms.length && !isLoadingTerms) ? (
              <form className="academic-year-form" onSubmit={handleSaveTerm}>
                <div className="user-form-heading"><span className="eyebrow">{editingTermId ? 'Update term' : 'New term'}</span><h3>{editingTermId ? 'Edit term dates' : 'Add term'}</h3></div>
                <div className="academic-year-grid">
                  <label className="form-field"><span>Academic year</span><select required disabled={editingTermId !== null} value={termForm.academic_year_id} onChange={(event) => setTermForm({ ...termForm, academic_year_id: event.target.value, start_date: '', end_date: '' })}><option value="">Select academic year</option>{managedAcademicYears.map((year) => <option key={year.id} value={year.id}>{year.name}</option>)}</select></label>
                  <label className="form-field"><span>Term name</span><input required maxLength={40} value={termForm.name} onChange={(event) => setTermForm({ ...termForm, name: event.target.value })} placeholder="e.g. Term 1" /></label>
                  <label className="form-field"><span>Start date</span><input required type="date" min={managedAcademicYears.find((year) => String(year.id) === termForm.academic_year_id)?.start_date} max={managedAcademicYears.find((year) => String(year.id) === termForm.academic_year_id)?.end_date} value={termForm.start_date} onChange={(event) => setTermForm({ ...termForm, start_date: event.target.value })} /></label>
                  <label className="form-field"><span>End date</span><input required type="date" min={termForm.start_date || managedAcademicYears.find((year) => String(year.id) === termForm.academic_year_id)?.start_date} max={managedAcademicYears.find((year) => String(year.id) === termForm.academic_year_id)?.end_date} value={termForm.end_date} onChange={(event) => setTermForm({ ...termForm, end_date: event.target.value })} /></label>
                  <label className="academic-year-active"><input type="checkbox" checked={termForm.is_active} onChange={(event) => setTermForm({ ...termForm, is_active: event.target.checked })} /><span>Mark this term active</span></label>
                </div>
                <div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isSavingTerm}>{isSavingTerm ? 'Saving...' : editingTermId ? 'Save changes' : 'Save term'}</button><button className="ghost-btn" type="button" onClick={() => { setEditingTermId(null); setShowTermForm(false); setTermForm(emptyTermForm); }} disabled={isSavingTerm}>Cancel</button></div>
              </form>
            ) : null}
            <div className="table-scroll academic-year-table-scroll">
              <table><thead><tr><th>Term</th><th>Academic year</th><th>Start date</th><th>End date</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>{managedTerms.map((term) => <tr key={term.id}><td><strong>{term.name}</strong></td><td>{term.academic_year.name}</td><td>{term.start_date}</td><td>{term.end_date}</td><td><span className={`account-status ${term.is_active ? 'active' : 'inactive'}`}>{term.is_active ? 'Active' : 'Inactive'}</span></td><td><button className="text-btn" type="button" onClick={() => startEditTerm(term)}>Edit</button></td></tr>)}
                  {!managedTerms.length && !isLoadingTerms ? <tr><td colSpan={6} className="empty-table">No terms have been set up.</td></tr> : null}
                </tbody>
              </table>
            </div>
            {isLoadingTerms ? <p className="empty-note">Loading terms...</p> : null}
          </section>
        ) : activeSection === 'Academic Years' && isAdminWorkspace ? (
          <section className="panel academic-year-panel">
            <div className="panel-header">
              <div><span className="eyebrow">School setup</span><h3>Academic years</h3></div>
              <button className="primary-btn" type="button" onClick={startCreateAcademicYear}>Add academic year</button>
            </div>
            <p className="empty-note academic-year-description">Create and maintain school sessions. Only one year can be active at a time; activating a year makes it the current session.</p>
            {academicYearError ? <p className="dashboard-error" role="alert">{academicYearError}</p> : null}
            {academicYearNotice ? <p className="user-management-notice" role="status">{academicYearNotice}</p> : null}
            {showAcademicYearForm || (!managedAcademicYears.length && !isLoadingAcademicYears) ? (
              <form className="academic-year-form" onSubmit={handleSaveAcademicYear}>
                <div className="user-form-heading"><span className="eyebrow">{editingAcademicYearId ? 'Update session' : 'New session'}</span><h3>{editingAcademicYearId ? 'Edit academic year' : 'Add academic year'}</h3></div>
                <div className="academic-year-grid">
                  <label className="form-field"><span>Academic year name</span><input required maxLength={20} value={academicYearForm.name} onChange={(event) => setAcademicYearForm({ ...academicYearForm, name: event.target.value })} placeholder="e.g. 2026/2027" /></label>
                  <label className="form-field"><span>Start date</span><input required type="date" value={academicYearForm.start_date} onChange={(event) => setAcademicYearForm({ ...academicYearForm, start_date: event.target.value })} /></label>
                  <label className="form-field"><span>End date</span><input required type="date" value={academicYearForm.end_date} min={academicYearForm.start_date || undefined} onChange={(event) => setAcademicYearForm({ ...academicYearForm, end_date: event.target.value })} /></label>
                  <label className="academic-year-active"><input type="checkbox" checked={academicYearForm.is_active} onChange={(event) => setAcademicYearForm({ ...academicYearForm, is_active: event.target.checked })} /><span>Set as the current active school year</span></label>
                </div>
                <div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isSavingAcademicYear}>{isSavingAcademicYear ? 'Saving...' : editingAcademicYearId ? 'Save changes' : 'Save academic year'}</button><button className="ghost-btn" type="button" onClick={() => { setEditingAcademicYearId(null); setShowAcademicYearForm(false); setAcademicYearForm(emptyAcademicYearForm); }} disabled={isSavingAcademicYear}>Cancel</button></div>
              </form>
            ) : null}
            <div className="table-scroll academic-year-table-scroll">
              <table><thead><tr><th>Academic year</th><th>Start date</th><th>End date</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>{managedAcademicYears.map((year) => <tr key={year.id}><td><strong>{year.name}</strong></td><td>{year.start_date}</td><td>{year.end_date}</td><td><span className={`account-status ${year.is_active ? 'active' : 'inactive'}`}>{year.is_active ? 'Current' : 'Inactive'}</span></td><td><button className="text-btn" type="button" onClick={() => startEditAcademicYear(year)}>Edit</button></td></tr>)}
                  {!managedAcademicYears.length && !isLoadingAcademicYears ? <tr><td colSpan={5} className="empty-table">No academic years have been set up.</td></tr> : null}
                </tbody>
              </table>
            </div>
            {isLoadingAcademicYears ? <p className="empty-note">Loading academic years...</p> : null}
          </section>
        ) : activeSection === 'Teachers' && ['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) ? (
          <section className="panel data-management-panel">
            <div className="panel-header"><div><span className="eyebrow">Staff records</span><h3>Teachers</h3></div>{isAdminWorkspace ? <div className="student-header-actions"><button className="ghost-btn" type="button" onClick={() => { setShowBulkImport((v) => !v); setBulkImportRole('TEACHER'); setBulkImportError(''); setBulkImportNotice(''); }}>Import CSV</button><button className="primary-btn" type="button" onClick={startDataManagementCreate}>Add teacher</button></div> : null}</div>
            <p className="empty-note data-management-description">Maintain teacher profiles and the staff records used for class and subject assignments.</p>
            {dataManagementError ? <p className="dashboard-error" role="alert">{dataManagementError}</p> : null}{dataManagementNotice ? <p className="user-management-notice" role="status">{dataManagementNotice}</p> : null}
            {bulkImportNotice && bulkImportRole === 'TEACHER' ? <p className="user-management-notice" role="status">{bulkImportNotice}</p> : null}
            {showBulkImport && bulkImportRole === 'TEACHER' ? (
              <form className="academic-year-form" onSubmit={handleBulkImport}>
                <div className="user-form-heading"><span className="eyebrow">CSV import</span><h3>Import teacher accounts</h3></div>
                <p className="empty-note" style={{ marginBottom: 10 }}>Required columns: <code>username, password, first_name, last_name, employee_id</code>. Optional: <code>email, department, qualification</code></p>
                {bulkImportError ? <p className="dashboard-error" role="alert">{bulkImportError}</p> : null}
                <label className="form-field"><span>Paste CSV data</span><textarea className="bulk-import-textarea" required rows={8} value={bulkImportCsv} onChange={(e) => setBulkImportCsv(e.target.value)} placeholder={`username,password,first_name,last_name,employee_id,department\njdoe,Pass1234!,John,Doe,T001,Science`} /></label>
                <div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isBulkImporting}>{isBulkImporting ? 'Importing...' : 'Import teachers'}</button><button className="ghost-btn" type="button" onClick={() => { setShowBulkImport(false); setBulkImportCsv(''); }}>Cancel</button></div>
              </form>
            ) : null}
            {showDataManagementForm ? <form className="academic-year-form" onSubmit={handleSaveDataManagementRecord}>
              <div className="user-form-heading"><span className="eyebrow">{editingDataRecordId ? 'Update profile' : 'New profile'}</span><h3>{editingDataRecordId ? 'Edit teacher' : 'Create teacher account'}</h3></div>
              <div className="academic-year-grid">
                {!editingDataRecordId ? <><label className="form-field"><span>Username</span><input required value={dataManagementForm.username} onChange={(event) => setDataManagementForm({ ...dataManagementForm, username: event.target.value })} /></label><label className="form-field"><span>Initial password</span><input required type="password" minLength={8} value={dataManagementForm.password} onChange={(event) => setDataManagementForm({ ...dataManagementForm, password: event.target.value })} /></label></> : null}
                <label className="form-field"><span>First name</span><input value={dataManagementForm.first_name} onChange={(event) => setDataManagementForm({ ...dataManagementForm, first_name: event.target.value })} /></label><label className="form-field"><span>Last name</span><input value={dataManagementForm.last_name} onChange={(event) => setDataManagementForm({ ...dataManagementForm, last_name: event.target.value })} /></label>
                <label className="form-field"><span>Email</span><input type="email" value={dataManagementForm.email} onChange={(event) => setDataManagementForm({ ...dataManagementForm, email: event.target.value })} /></label><label className="form-field"><span>Employee ID</span><input required maxLength={20} value={dataManagementForm.employee_id} onChange={(event) => setDataManagementForm({ ...dataManagementForm, employee_id: event.target.value })} /></label>
                <label className="form-field"><span>Department</span><input value={dataManagementForm.department} onChange={(event) => setDataManagementForm({ ...dataManagementForm, department: event.target.value })} /></label><label className="form-field"><span>Qualification</span><input value={dataManagementForm.qualification} onChange={(event) => setDataManagementForm({ ...dataManagementForm, qualification: event.target.value })} /></label>
                <label className="form-field"><span>Phone number</span><input value={dataManagementForm.phone_number} onChange={(event) => setDataManagementForm({ ...dataManagementForm, phone_number: event.target.value })} /></label>
                {editingDataRecordId ? <label className="form-field"><span>Reset password (optional)</span><input type="password" minLength={8} value={dataManagementForm.password} onChange={(event) => setDataManagementForm({ ...dataManagementForm, password: event.target.value })} /></label> : null}
              </div><div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isSavingDataManagement}>{isSavingDataManagement ? 'Saving...' : editingDataRecordId ? 'Save changes' : 'Create teacher'}</button><button className="ghost-btn" type="button" onClick={() => { setShowDataManagementForm(false); setEditingDataRecordId(null); }}>Cancel</button></div>
            </form> : null}
            <div className="table-scroll"><table className="data-management-table"><thead><tr><th>Employee ID</th><th>Name</th><th>Username</th><th>Department</th><th>Qualification</th><th>Actions</th></tr></thead><tbody>
              {managedTeachers.map((teacher) => <tr key={teacher.id}><td>{teacher.employee_id}</td><td>{teacher.full_name}</td><td>{teacher.user.username}</td><td>{teacher.department || '—'}</td><td>{teacher.qualification || '—'}</td><td>{isAdminWorkspace ? <button className="text-btn" type="button" onClick={() => startDataManagementEdit(teacher)}>Edit</button> : 'View only'}</td></tr>)}
              {!managedTeachers.length && !isLoadingDataManagement ? <tr><td colSpan={6} className="empty-table">No teachers found.</td></tr> : null}
            </tbody></table></div>{isLoadingDataManagement ? <p className="empty-note">Loading teachers...</p> : null}
          </section>
        ) : activeSection === 'Classes' && ['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) ? (
          <section className="panel data-management-panel">
            <div className="panel-header"><div><span className="eyebrow">Academic structure</span><h3>Classes</h3></div>{['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) ? <button className="primary-btn" type="button" onClick={startDataManagementCreate}>Add class</button> : null}</div>
            <p className="empty-note data-management-description">Set up classes by academic year and assign a class teacher.</p>
            {dataManagementError ? <p className="dashboard-error" role="alert">{dataManagementError}</p> : null}{dataManagementNotice ? <p className="user-management-notice" role="status">{dataManagementNotice}</p> : null}
            {showDataManagementForm ? <form className="academic-year-form" onSubmit={handleSaveDataManagementRecord}><div className="user-form-heading"><span className="eyebrow">{editingDataRecordId ? 'Update class' : 'New class'}</span><h3>{editingDataRecordId ? 'Edit class details' : 'Add class'}</h3></div><div className="academic-year-grid">
              <label className="form-field"><span>Class name</span><input required maxLength={80} value={dataManagementForm.name} onChange={(event) => setDataManagementForm({ ...dataManagementForm, name: event.target.value })} placeholder="e.g. Form 1" /></label><label className="form-field"><span>Section</span><input maxLength={40} value={dataManagementForm.section} onChange={(event) => setDataManagementForm({ ...dataManagementForm, section: event.target.value })} placeholder="Optional" /></label>
              <label className="form-field"><span>Academic year</span><select required disabled={editingDataRecordId !== null} value={dataManagementForm.academic_year_id} onChange={(event) => setDataManagementForm({ ...dataManagementForm, academic_year_id: event.target.value })}><option value="">Select year</option>{managedAcademicYears.map((year) => <option key={year.id} value={year.id}>{year.name}</option>)}</select></label><label className="form-field"><span>Class teacher</span><select value={dataManagementForm.teacher_id} onChange={(event) => setDataManagementForm({ ...dataManagementForm, teacher_id: event.target.value })}><option value="">Unassigned</option>{managedTeachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.full_name} ({teacher.employee_id})</option>)}</select></label>
              <label className="academic-year-active"><input type="checkbox" checked={dataManagementForm.is_active} onChange={(event) => setDataManagementForm({ ...dataManagementForm, is_active: event.target.checked })} /><span>Class is active</span></label>
            </div><div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isSavingDataManagement}>{isSavingDataManagement ? 'Saving...' : editingDataRecordId ? 'Save changes' : 'Save class'}</button><button className="ghost-btn" type="button" onClick={() => { setShowDataManagementForm(false); setEditingDataRecordId(null); }}>Cancel</button></div></form> : null}
            <div className="table-scroll"><table className="data-management-table"><thead><tr><th>Class</th><th>Year</th><th>Class teacher</th><th>Status</th><th>Actions</th></tr></thead><tbody>{managedClasses.map((schoolClass) => <tr key={schoolClass.id}><td>{schoolClass.name}{schoolClass.section ? ` ${schoolClass.section}` : ''}</td><td>{schoolClass.academic_year.name}</td><td>{schoolClass.teacher || 'Unassigned'}</td><td><span className={`account-status ${schoolClass.is_active ? 'active' : 'inactive'}`}>{schoolClass.is_active ? 'Active' : 'Inactive'}</span></td><td><button className="text-btn" type="button" onClick={() => startDataManagementEdit(schoolClass)}>Edit</button></td></tr>)}{!managedClasses.length && !isLoadingDataManagement ? <tr><td colSpan={5} className="empty-table">No classes found.</td></tr> : null}</tbody></table></div>{isLoadingDataManagement ? <p className="empty-note">Loading classes...</p> : null}
          </section>
        ) : activeSection === 'Subjects' && ['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) ? (
          <section className="panel data-management-panel">
            <div className="panel-header"><div><span className="eyebrow">Curriculum</span><h3>Subjects</h3></div><button className="primary-btn" type="button" onClick={startDataManagementCreate}>Add subject</button></div>
            <p className="empty-note data-management-description">Attach subjects to a class and assign the teacher responsible for entering marks.</p>
            {dataManagementError ? <p className="dashboard-error" role="alert">{dataManagementError}</p> : null}{dataManagementNotice ? <p className="user-management-notice" role="status">{dataManagementNotice}</p> : null}
            {showDataManagementForm ? <form className="academic-year-form" onSubmit={handleSaveDataManagementRecord}><div className="user-form-heading"><span className="eyebrow">{editingDataRecordId ? 'Update subject' : 'New subject'}</span><h3>{editingDataRecordId ? 'Edit subject details' : 'Add subject'}</h3></div><div className="academic-year-grid">
              <label className="form-field"><span>Subject code</span><input required maxLength={20} value={dataManagementForm.code} onChange={(event) => setDataManagementForm({ ...dataManagementForm, code: event.target.value })} /></label><label className="form-field"><span>Subject name</span><input required maxLength={120} value={dataManagementForm.name} onChange={(event) => setDataManagementForm({ ...dataManagementForm, name: event.target.value })} /></label>
              <label className="form-field"><span>Class</span><select required value={dataManagementForm.school_class_id} onChange={(event) => setDataManagementForm({ ...dataManagementForm, school_class_id: event.target.value })}><option value="">Select class</option>{managedClasses.map((schoolClass) => <option key={schoolClass.id} value={schoolClass.id}>{schoolClass.name}{schoolClass.section ? ` ${schoolClass.section}` : ''} · {schoolClass.academic_year.name}</option>)}</select></label><label className="form-field"><span>Assigned teacher</span><select value={dataManagementForm.teacher_id} onChange={(event) => setDataManagementForm({ ...dataManagementForm, teacher_id: event.target.value })}><option value="">Unassigned</option>{managedTeachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.full_name} ({teacher.employee_id})</option>)}</select></label>
              <label className="form-field"><span>Description</span><textarea rows={2} value={dataManagementForm.description} onChange={(event) => setDataManagementForm({ ...dataManagementForm, description: event.target.value })} /></label>
            </div><div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isSavingDataManagement}>{isSavingDataManagement ? 'Saving...' : editingDataRecordId ? 'Save changes' : 'Save subject'}</button><button className="ghost-btn" type="button" onClick={() => { setShowDataManagementForm(false); setEditingDataRecordId(null); }}>Cancel</button></div></form> : null}
            <div className="table-scroll"><table className="data-management-table"><thead><tr><th>Code</th><th>Subject</th><th>Class</th><th>Teacher</th><th>Description</th><th>Actions</th></tr></thead><tbody>{managedSubjects.map((subject) => <tr key={subject.id}><td>{subject.code}</td><td>{subject.name}</td><td>{subject.school_class.name} · {subject.school_class.academic_year.name}</td><td>{subject.teacher || 'Unassigned'}</td><td>{subject.description || '—'}</td><td><button className="text-btn" type="button" onClick={() => startDataManagementEdit(subject)}>Edit</button></td></tr>)}{!managedSubjects.length && !isLoadingDataManagement ? <tr><td colSpan={6} className="empty-table">No subjects found.</td></tr> : null}</tbody></table></div>{isLoadingDataManagement ? <p className="empty-note">Loading subjects...</p> : null}
          </section>
        ) : activeSection === 'Results' && ['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER', 'TEACHER'].includes(user.role) ? (
          <section className="panel result-workspace">
            <div className="panel-header result-workspace-header">
              <div><span className="eyebrow">Mark entry and review</span><h3>Results workflow</h3></div>
              <label className="result-filter"><span>Filter status</span><select value={resultStatusFilter} onChange={(event) => setResultStatusFilter(event.target.value)}>
                <option value="">All statuses</option>
                <option value="REVIEW_QUEUE">Review queue</option>
                <option value="PENDING">Pending action</option>
                <option value="APPROVED_PUBLISHED">Approved / published</option>
                {['DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'PUBLISHED'].map((status) => <option key={status} value={status}>{status.replace('_', ' ')}</option>)}
              </select></label>
            </div>
            <p className="empty-note result-workflow-help">Teachers save marks as drafts and submit them for review. An administrator or academic officer reviews, approves, and publishes results. Students only see published results.</p>
            {resultError ? <p className="dashboard-error" role="alert">{resultError}</p> : null}
            {resultNotice ? <p className="user-management-notice" role="status">{resultNotice}</p> : null}
            {['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) ? (
              <div className="bulk-action-bar">
                <span className="bulk-action-count">{bulkApprovalIds.size} selected</span>
                {bulkApprovalError ? <p className="dashboard-error" role="alert" style={{ margin: 0 }}>{bulkApprovalError}</p> : null}
                {bulkApprovalNotice ? <p className="user-management-notice" role="status" style={{ margin: 0 }}>{bulkApprovalNotice}</p> : null}
                {bulkApprovalIds.size > 0 ? (
                  <>
                    <input
                      className="bulk-approval-comment"
                      type="text"
                      placeholder="Comment (required to return)"
                      value={bulkApprovalComments}
                      onChange={(e) => setBulkApprovalComments(e.target.value)}
                    />
                    <button className="ghost-btn" type="button" disabled={isBulkApproving} onClick={() => handleBulkApprove('approve')}>Approve selected</button>
                    <button className="ghost-btn" type="button" disabled={isBulkApproving || !bulkApprovalComments.trim()} onClick={() => handleBulkApprove('return')}>Return selected</button>
                    {['SUPER_ADMIN', 'ADMIN'].includes(user.role) ? <button className="ghost-btn" type="button" disabled={isBulkApproving} onClick={() => handleBulkApprove('publish')}>Publish selected</button> : null}
                    <button className="text-btn" type="button" onClick={() => setBulkApprovalIds(new Set())}>Clear</button>
                  </>
                ) : <span className="bulk-action-hint">Check rows below to bulk approve / return / publish</span>}
              </div>
            ) : null}
            {user.role === 'TEACHER' && editingResultId === null ? (
              <div className="result-entry-form">
                <div className="result-entry-title"><span className="eyebrow">Teacher mark entry</span><h4>Bulk mark entry</h4></div>
                {resultOptionsError ? <p className="dashboard-error" role="alert">{resultOptionsError}</p> : null}
                {bulkError ? <p className="dashboard-error" role="alert">{bulkError}</p> : null}
                {bulkNotice ? <p className="user-management-notice" role="status">{bulkNotice}</p> : null}
                <div className="result-entry-grid" style={{ marginBottom: 14 }}>
                  <label className="form-field"><span>Academic year</span>
                    <select value={bulkContext.academic_year_id} onChange={(e) => setBulkContext({ ...bulkContext, academic_year_id: e.target.value, term_id: '', subject_id: '' })}>
                      <option value="">Select year</option>{resultYears.map((y) => <option key={y.id} value={y.id}>{y.name}</option>)}
                    </select>
                  </label>
                  <label className="form-field"><span>Term</span>
                    <select disabled={!bulkContext.academic_year_id} value={bulkContext.term_id} onChange={(e) => setBulkContext({ ...bulkContext, term_id: e.target.value })}>
                      <option value="">Select term</option>{resultTerms.filter((t) => String(t.academic_year.id) === bulkContext.academic_year_id).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  </label>
                  <label className="form-field"><span>Subject</span>
                    <select value={bulkContext.subject_id} onChange={(e) => setBulkContext({ ...bulkContext, subject_id: e.target.value })}>
                      <option value="">Select subject</option>{resultSubjects.map((s) => <option key={s.id} value={s.id}>{s.code} · {s.name} ({s.school_class.name})</option>)}
                    </select>
                  </label>
                  <label className="form-field"><span>Assessment type</span>
                    <input maxLength={40} value={bulkContext.assessment_type} onChange={(e) => setBulkContext({ ...bulkContext, assessment_type: e.target.value })} placeholder="e.g. CAT 1" />
                  </label>
                </div>
                {bulkRows.length > 0 ? (
                  <>
                    <div className="table-scroll" style={{ marginBottom: 12 }}>
                      <table className="bulk-entry-table">
                        <thead><tr><th>#</th><th>Admission</th><th>Student name</th><th>Marks (0–100)</th><th>Remarks</th></tr></thead>
                        <tbody>
                          {bulkRows.map((row, i) => (
                            <tr key={row.student_id}>
                              <td>{i + 1}</td>
                              <td>{row.admission}</td>
                              <td><strong>{row.name}</strong></td>
                              <td><input className="bulk-marks-input" type="number" min="0" max="100" step="0.01" placeholder="—" value={row.marks}
                                onChange={(e) => setBulkRows((prev) => prev.map((r, idx) => idx === i ? { ...r, marks: e.target.value } : r))}
                                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); const next = document.querySelectorAll<HTMLInputElement>('.bulk-marks-input')[i + 1]; next?.focus(); } }}
                              /></td>
                              <td><input className="bulk-remarks-input" type="text" maxLength={200} placeholder="Optional" value={row.remarks}
                                onChange={(e) => setBulkRows((prev) => prev.map((r, idx) => idx === i ? { ...r, remarks: e.target.value } : r))}
                              /></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="user-form-actions">
                      <button className="primary-btn" type="button" disabled={isSavingBulk} onClick={() => handleBulkSave(true)}>{isSavingBulk ? 'Saving...' : `Submit all ${bulkRows.length} for review`}</button>
                      <button className="ghost-btn" type="button" disabled={isSavingBulk} onClick={() => handleBulkSave(false)}>Save as drafts</button>
                    </div>
                  </>
                ) : bulkContext.subject_id && bulkContext.term_id ? (
                  <p className="empty-note">No enrolled students found for this subject and term.</p>
                ) : (
                  <p className="empty-note">Select year, term, and subject to load the student list.</p>
                )}
              </div>
            ) : null}
            {editingResultId !== null ? (
              <form className="result-entry-form" onSubmit={handleSaveResult}>
                <div className="result-entry-title"><div><span className="eyebrow">Correct result</span><h4>Update marks and remarks</h4></div></div>
                {resultOptionsError ? <p className="dashboard-error" role="alert">Could not load mark entry options. {resultOptionsError}</p> : null}
                <div className="result-entry-grid">
                  <label className="form-field"><span>Academic year</span><select required disabled value={resultForm.academic_year_id}><option value="">Select year</option>{resultYears.map((year) => <option key={year.id} value={year.id}>{year.name}</option>)}</select></label>
                  <label className="form-field"><span>Term</span><select required disabled value={resultForm.term_id}><option value="">Select term</option>{resultTerms.filter((term) => String(term.academic_year.id) === resultForm.academic_year_id).map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}</select></label>
                  <label className="form-field"><span>Subject</span><select required disabled value={resultForm.subject_id}><option value="">Select assigned subject</option>{resultSubjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.code} · {subject.name} ({subject.school_class.name})</option>)}</select></label>
                  <label className="form-field"><span>Student</span><select required disabled value={resultForm.student_id}><option value="">Select student</option>{resultEnrollments.map((enrollment) => <option key={enrollment.student.id} value={enrollment.student.id}>{enrollment.student.full_name} ({enrollment.student.admission_number})</option>)}</select></label>
                  <label className="form-field"><span>Assessment</span><input required maxLength={40} value={resultForm.assessment_type} disabled onChange={(event) => setResultForm({ ...resultForm, assessment_type: event.target.value })} /></label>
                  <label className="form-field"><span>Marks (0–100)</span><input required type="number" min="0" max="100" step="0.01" value={resultForm.marks} onChange={(event) => setResultForm({ ...resultForm, marks: event.target.value })} /></label>
                  <label className="form-field result-remarks"><span>Remarks</span><textarea maxLength={2000} rows={2} value={resultForm.remarks} onChange={(event) => setResultForm({ ...resultForm, remarks: event.target.value })} /></label>
                </div>
                <div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isSavingResult}>{isSavingResult ? 'Saving...' : 'Save correction'}</button><button className="ghost-btn" type="button" onClick={() => { setEditingResultId(null); setResultForm(emptyResultForm); }}>Cancel</button></div>
              </form>
            ) : null}
            <div className="table-scroll result-table-scroll">
              <table className="result-table">
                <thead><tr>{['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) ? <th><input type="checkbox" aria-label="Select all" checked={bulkApprovalIds.size > 0 && resultRows.every((r) => bulkApprovalIds.has(r.id))} onChange={(e) => setBulkApprovalIds(e.target.checked ? new Set(resultRows.map((r) => r.id)) : new Set())} /></th> : null}<th>Student</th><th>Subject</th><th>Assessment</th><th>Marks</th><th>Grade</th><th>Status</th><th>Workflow actions</th><th>Review history</th></tr></thead>
                <tbody>{resultRows.map((result) => {
                  const isTeacher = user.role === 'TEACHER';
                  const isReviewer = ['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) && result.entered_by?.username !== user.username;
                  const canPublish = ['SUPER_ADMIN', 'ADMIN'].includes(user.role) && result.entered_by?.username !== user.username;
                  const canEdit = isTeacher && ['DRAFT', 'RETURNED'].includes(result.status);
                  return <tr key={result.id}>
                    {['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) ? <td><input type="checkbox" aria-label={`Select result ${result.id}`} checked={bulkApprovalIds.has(result.id)} onChange={(e) => setBulkApprovalIds((prev) => { const next = new Set(prev); e.target.checked ? next.add(result.id) : next.delete(result.id); return next; })} /></td> : null}
                    <td><strong>{result.student?.full_name}</strong><small>{result.student?.admission_number}</small></td>
                    <td>{result.subject?.code} · {result.subject?.name}<small>{result.academic_year?.name} / {result.term?.name}</small></td>
                    <td>{result.assessment_type || '—'}</td><td>{result.marks}</td><td><span className="grade-badge">{result.grade}</span></td>
                    <td><span className={`status-pill ${result.status.toLowerCase()}`}>{result.status.replace('_', ' ')}</span></td>
                    <td><div className="result-actions">
                      {canEdit ? <button className="text-btn" type="button" onClick={() => beginResultEdit(result)}>Edit</button> : null}
                      {isTeacher && result.status === 'DRAFT' ? <button className="text-btn" type="button" onClick={() => handleResultStatusChange(result, 'SUBMITTED')}>Submit for review</button> : null}
                      {isTeacher && result.status === 'RETURNED' ? <button className="text-btn" type="button" onClick={() => handleResultStatusChange(result, 'SUBMITTED')}>Re-submit</button> : null}
                      {isReviewer && result.status === 'SUBMITTED' ? <button className="text-btn" type="button" onClick={() => handleResultStatusChange(result, 'UNDER_REVIEW')}>Start review</button> : null}
                      {isReviewer && result.status === 'UNDER_REVIEW' ? <>
                        <textarea aria-label={`Review comment for result ${result.id}`} rows={2} maxLength={2000} value={reviewComments[result.id] || ''} onChange={(event) => setReviewComments({ ...reviewComments, [result.id]: event.target.value })} placeholder="Comment required to return" />
                        <button className="text-btn" type="button" onClick={() => handleResultStatusChange(result, 'APPROVED')}>Approve</button>
                        <button className="text-btn danger-text-btn" type="button" disabled={!(reviewComments[result.id] || '').trim()} onClick={() => handleResultStatusChange(result, 'RETURNED')}>Return</button>
                      </> : null}
                      {canPublish && result.status === 'APPROVED' ? <button className="text-btn" type="button" onClick={() => handleResultStatusChange(result, 'PUBLISHED')}>Publish</button> : null}
                    </div></td>
                    <td className="result-history-cell">{result.approvals?.length ? <details><summary>Review history ({result.approvals.length})</summary><ul>{result.approvals.map((approval) => <li key={approval.id}><strong>{approval.decision.replace('_', ' ')}</strong> by {approval.approved_by_name}{approval.comments ? <p>{approval.comments}</p> : null}<small>{new Date(approval.created_at).toLocaleString()}</small></li>)}</ul></details> : <small>No review activity</small>}</td>
                  </tr>;
                })}{!resultRows.length && !isLoadingResults ? <tr><td colSpan={8} className="empty-table">No results match this status.</td></tr> : null}</tbody>
              </table>
            </div>
            {isLoadingResults ? <p className="empty-note">Loading results...</p> : null}
          </section>
        ) : activeSection === 'Users' && ['SUPER_ADMIN', 'ADMIN'].includes(user.role) ? (
          <section className="panel user-management-panel">
            <div className="panel-header">
              <div><span className="eyebrow">Accounts and access</span><h3>Manage user accounts</h3></div>
              <button className="primary-btn" type="button" onClick={startCreateUser}>Add user</button>
            </div>
            <p className="empty-note user-management-description">
              Create accounts, assign roles, update account details, and review access status.
              {user.role === 'SUPER_ADMIN' ? ' Super Admin accounts cannot disable their own access or the last active Super Admin.' : ' Only a Super Admin can grant administrator roles or change account status.'}
            </p>
            {userManagementError ? <p className="dashboard-error" role="alert">{userManagementError}</p> : null}
            {userManagementNotice ? <p className="user-management-notice" role="status">{userManagementNotice}</p> : null}
            {showUserForm ? (
              <form className="user-form" onSubmit={handleSaveUser}>
                <div className="panel-header user-form-heading">
                  <div>
                    <span className="eyebrow">{editingUserId ? 'Edit account' : 'New account'}</span>
                    <h3>{editingUserId ? 'Update user details' : 'Create a user account'}</h3>
                    <p>Set up profile details, credentials, and the right level of access for this account.</p>
                  </div>
                </div>
                <div className="user-form-grid">
                  <label className="form-field"><span>Username</span><input autoComplete="off" required placeholder="e.g. janesmith" value={userForm.username} onChange={(event) => setUserForm({ ...userForm, username: event.target.value })} /></label>
                  <label className="form-field"><span>Role</span><select required value={userForm.role} disabled={editingUserId === user.id && user.role === 'SUPER_ADMIN'} onChange={(event) => setUserForm({ ...userForm, role: event.target.value as Role })}>
                    {roleOptions.filter((option) => user.role === 'SUPER_ADMIN' || !['SUPER_ADMIN', 'ADMIN'].includes(option.role)).map((option) => <option key={option.role} value={option.role}>{option.label}</option>)}
                  </select></label>
                  <label className="form-field"><span>First name</span><input value={userForm.first_name} onChange={(event) => setUserForm({ ...userForm, first_name: event.target.value })} /></label>
                  <label className="form-field"><span>Last name</span><input value={userForm.last_name} onChange={(event) => setUserForm({ ...userForm, last_name: event.target.value })} /></label>
                  <label className="form-field"><span>Email</span><input type="email" value={userForm.email} onChange={(event) => setUserForm({ ...userForm, email: event.target.value })} /></label>
                  <label className="form-field"><span>Phone number</span><input value={userForm.phone_number} onChange={(event) => setUserForm({ ...userForm, phone_number: event.target.value })} /></label>
                  <label className="form-field"><span>{editingUserId ? 'New password (optional)' : 'Password'}</span><input autoComplete="new-password" minLength={8} required={!editingUserId} type="password" value={userForm.password} onChange={(event) => setUserForm({ ...userForm, password: event.target.value })} /></label>
                </div>
                <div className="user-form-actions">
                  <button className="primary-btn" type="submit" disabled={isSavingUser}>{isSavingUser ? 'Saving...' : editingUserId ? 'Save changes' : 'Create account'}</button>
                  <button className="ghost-btn" type="button" onClick={() => setShowUserForm(false)} disabled={isSavingUser}>Cancel</button>
                </div>
              </form>
            ) : null}
            <div className="table-scroll">
              <table>
                <thead><tr><th>Username</th><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>
                  {managedUsers.map((account) => (
                    <tr key={account.id}>
                      <td>{account.username}</td>
                      <td>{[account.first_name, account.last_name].filter(Boolean).join(' ') || '—'}</td>
                      <td>{account.email || '—'}</td>
                      <td>{roleOptions.find((option) => option.role === account.role)?.label || account.role}</td>
                      <td><span className={`account-status ${account.is_active ? 'active' : 'inactive'}`}>{account.is_active ? 'Active' : 'Disabled'}</span></td>
                      <td className="user-actions">
                        <button className="text-btn" type="button" onClick={() => startEditUser(account)}>Edit</button>
                        {(() => {
                          const isSelf = account.id === user.id;
                          const targetIsAdmin = ['SUPER_ADMIN', 'ADMIN'].includes(account.role);
                          const canDisable = !isSelf && account.is_active && (
                            user.role === 'SUPER_ADMIN' || (user.role === 'ADMIN' && !targetIsAdmin)
                          );
                          const canReactivate = !isSelf && !account.is_active && (
                            user.role === 'SUPER_ADMIN' || (user.role === 'ADMIN' && !targetIsAdmin)
                          );
                          return <>
                            {canDisable ? <button className="text-btn danger-text-btn" type="button" onClick={() => handleUserStatusChange(account, false)}>Disable</button> : null}
                            {canReactivate ? <button className="text-btn" type="button" onClick={() => handleUserStatusChange(account, true)}>Reactivate</button> : null}
                          </>;
                        })()}
                      </td>
                    </tr>
                  ))}
                  {!managedUsers.length && !isLoadingUsers ? <tr><td colSpan={6} className="empty-table">No user accounts found.</td></tr> : null}
                </tbody>
              </table>
            </div>
            {isLoadingUsers ? <p className="empty-note">Loading user accounts...</p> : null}
          </section>
        ) : activeSection === 'My Classes' && user.role === 'TEACHER' ? (
          <section className="panel data-management-panel">
            <div className="panel-header"><div><span className="eyebrow">Teaching assignments</span><h3>My classes</h3></div></div>
            <p className="empty-note data-management-description">Classes assigned to you directly or through subjects you teach.</p>
            {teacherClassesError ? <p className="dashboard-error" role="alert">{teacherClassesError}</p> : null}
            {isLoadingTeacherClasses ? <p className="empty-note" role="status">Loading assigned classes...</p> : null}
            <div className="table-scroll"><table className="data-management-table"><thead><tr><th>Class</th><th>Academic year</th><th>Class teacher</th><th>Roster</th></tr></thead><tbody>
              {teacherClasses.map((schoolClass) => <tr key={schoolClass.id}><td><strong>{schoolClass.name}{schoolClass.section ? ` ${schoolClass.section}` : ''}</strong></td><td>{schoolClass.academic_year.name}</td><td>{schoolClass.teacher || 'Unassigned'}</td><td><button className="text-btn" type="button" onClick={() => openClassRoster(schoolClass)}>View students</button></td></tr>)}
              {!teacherClasses.length && !isLoadingTeacherClasses && !teacherClassesError ? <tr><td colSpan={4} className="empty-table">No classes are assigned to your account yet.</td></tr> : null}
            </tbody></table></div>
          </section>
        ) : activeSection === 'My Subjects' && user.role === 'TEACHER' ? (
          <section className="panel data-management-panel">
            <div className="panel-header"><div><span className="eyebrow">Teaching assignments</span><h3>My subjects</h3></div></div>
            <p className="empty-note data-management-description">Subjects assigned to your teacher account.</p>
            {teacherClassesError ? <p className="dashboard-error" role="alert">{teacherClassesError}</p> : null}
            {isLoadingTeacherClasses ? <p className="empty-note" role="status">Loading assigned subjects...</p> : null}
            <div className="table-scroll"><table className="data-management-table"><thead><tr><th>Code</th><th>Subject</th><th>Class</th><th>Academic year</th></tr></thead><tbody>
              {teacherSubjects.map((subject) => <tr key={subject.id}><td>{subject.code}</td><td><strong>{subject.name}</strong></td><td>{subject.school_class.name}</td><td>{subject.school_class.academic_year.name}</td></tr>)}
              {!teacherSubjects.length && !isLoadingTeacherClasses && !teacherClassesError ? <tr><td colSpan={4} className="empty-table">No subjects are assigned to your account yet.</td></tr> : null}
            </tbody></table></div>
          </section>
        ) : activeSection === 'Reports' && ['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER', 'TEACHER'].includes(user.role) ? (
          <div id="report-print-area" className="report-print-area">
            {reportError ? <p className="dashboard-error" role="alert">{reportError}</p> : null}
            {dashboardError ? <p className="dashboard-error" role="alert">{dashboardError}</p> : null}
            {isLoadingDashboard ? <p className="empty-note" role="status">Loading workspace totals...</p> : null}
            <section className="stats-grid report-stats-grid">
              <article className="stat-card primary"><div><span>Students in your workspace</span><strong>{dashboard.stats.students}</strong></div></article>
              <article className="stat-card success"><div><span>Approved or published results</span><strong>{dashboard.stats.approved_results}</strong></div></article>
              <article className="stat-card warning"><div><span>Results awaiting action</span><strong>{dashboard.stats.pending_results}</strong></div></article>
            </section>
            <section className="panel report-panel">
              <div className="panel-header report-panel-header"><div><span className="eyebrow">Approved performance</span><h3>Subject performance</h3></div><div className="report-actions"><button className="ghost-btn" type="button" onClick={exportPerformanceReport} disabled={!reportSubjects.length}>Export CSV</button><button className="ghost-btn" type="button" onClick={() => window.print()}>Print report</button></div></div>
              <p className="empty-note report-description">Average marks and student counts use approved and published results. Teacher reports include assigned subjects and classes.</p>
              {isLoadingReport ? <p className="empty-note" role="status">Loading performance report...</p> : null}
              <div className="table-scroll"><table className="report-subject-table"><thead><tr><th>Subject</th><th>Average marks</th><th>Students</th><th>Performance</th></tr></thead><tbody>
                {reportSubjects.map((subject) => <tr key={subject.code}><td><strong>{subject.name}</strong><small className="report-subject-code">{subject.code}</small></td><td>{subject.average_marks.toFixed(1)}%</td><td>{subject.total_students}</td><td><div className="report-meter" role="img" aria-label={`${subject.average_marks.toFixed(1)} percent average`}><span style={{ width: `${Math.max(0, Math.min(100, subject.average_marks))}%` }} /></div></td></tr>)}
                {!reportSubjects.length && !isLoadingReport && !reportError ? <tr><td colSpan={4} className="empty-table">No approved or published subject results are available yet.</td></tr> : null}
              </tbody></table></div>
            </section>
            <section className="panel table-panel report-leaders-panel">
              <div className="panel-header"><div><span className="eyebrow">Approved and published results</span><h3>Top student averages</h3></div></div>
              <div className="table-scroll"><table><thead><tr><th>Rank</th><th>Student</th><th>Admission number</th><th>Average</th></tr></thead><tbody>
                {dashboard.top_students.map((student, index) => <tr key={student.admission_number}><td>{index + 1}</td><td>{student.name}</td><td>{student.admission_number}</td><td><span className="grade-badge">{student.average.toFixed(1)}%</span></td></tr>)}
                {!dashboard.top_students.length ? <tr><td colSpan={4} className="empty-table">No student performance data is available yet.</td></tr> : null}
              </tbody></table></div>
            </section>
          </div>
        ) : activeSection === 'Audit Logs' && ['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) ? (
          <section className="panel user-management-panel audit-log-panel">
            <div className="panel-header"><div><span className="eyebrow">Security and accountability</span><h3>Recent activity</h3></div><span className="audit-log-count">{auditLogs.length} entr{auditLogs.length === 1 ? 'y' : 'ies'}</span></div>
            <p className="empty-note user-management-description">Review account, academic structure, and result workflow changes. The newest activity appears first.</p>
            <div className="audit-log-filters">
              <label className="form-field"><span>Action</span><select value={auditActionFilter} onChange={(event) => setAuditActionFilter(event.target.value)}><option value="">All actions</option>{['CREATE', 'UPDATE', 'DISABLE', 'DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'PUBLISHED'].map((action) => <option key={action} value={action}>{action.replace('_', ' ')}</option>)}</select></label>
              <label className="form-field"><span>Record type</span><select value={auditModelFilter} onChange={(event) => setAuditModelFilter(event.target.value)}><option value="">All record types</option>{['User', 'Student', 'Teacher', 'SchoolClass', 'Subject', 'AcademicYear', 'Term', 'Enrollment', 'Result'].map((model) => <option key={model} value={model}>{model === 'SchoolClass' ? 'Class' : model}</option>)}</select></label>
              <label className="form-field"><span>Show latest</span><select value={auditLimit} onChange={(event) => setAuditLimit(event.target.value)}><option value="50">50 records</option><option value="100">100 records</option><option value="200">200 records</option></select></label>
            </div>
            {auditLogError ? <p className="dashboard-error" role="alert">{auditLogError}</p> : null}
            {isLoadingAuditLogs ? <p className="empty-note" role="status">Loading audit activity...</p> : null}
            <div className="table-scroll"><table className="audit-log-table"><thead><tr><th>Date and time</th><th>Actor</th><th>Action</th><th>Record type</th><th>Details</th></tr></thead><tbody>
              {auditLogs.map((entry) => <tr key={entry.id}><td>{new Date(entry.created_at).toLocaleString()}</td><td>{entry.actor_name || 'System'}</td><td><span className={`status-pill ${entry.action.toLowerCase()}`}>{entry.action.replace(/_/g, ' ')}</span></td><td>{entry.model_name === 'SchoolClass' ? 'Class' : entry.model_name}</td><td className="audit-log-description">{entry.description || '—'}</td></tr>)}
              {!auditLogs.length && !isLoadingAuditLogs && !auditLogError ? <tr><td colSpan={5} className="empty-table">No audit activity matches these filters.</td></tr> : null}
            </tbody></table></div>
          </section>
        ) : activeSection === 'Students' && ['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER', 'TEACHER', 'STUDENT'].includes(user.role) ? (
          <>
            {studentPageError ? <p className="dashboard-error" role="alert">{studentPageError}</p> : null}
            <section className="panel table-panel">
              <div className="panel-header">
                <div><span className="eyebrow">School records</span><h3>{selectedStudent ? selectedStudent.full_name : 'Students'}</h3></div>
                {selectedStudent ? user.role !== 'STUDENT' ? <button className="ghost-btn" type="button" onClick={() => setSelectedStudent(null)}>Back to students</button> : null : isAdminWorkspace ? <div className="student-header-actions"><button className="ghost-btn" type="button" onClick={() => { setShowBulkImport((v) => !v); setBulkImportRole('STUDENT'); setBulkImportError(''); setBulkImportNotice(''); setShowBulkEnrollForm(false); }}>Import CSV</button><button className="ghost-btn" type="button" onClick={() => { setShowBulkEnrollForm((v) => !v); setShowEnrollmentForm(false); setBulkEnrollError(''); setShowBulkImport(false); }}>Bulk enroll</button><button className="ghost-btn" type="button" onClick={() => { setEnrollmentForm(emptyEnrollmentForm); setEnrollmentError(''); setShowEnrollmentForm((shown) => !shown); setShowBulkEnrollForm(false); setShowBulkImport(false); }}>Enroll student</button><button className="primary-btn" type="button" onClick={startDataManagementCreate}>Add student</button></div> : null}
              </div>
              {!selectedStudent ? (
                <>
                  {dataManagementError ? <p className="dashboard-error" role="alert">{dataManagementError}</p> : null}{dataManagementNotice ? <p className="user-management-notice" role="status">{dataManagementNotice}</p> : null}
                  {bulkEnrollNotice ? <p className="user-management-notice" role="status">{bulkEnrollNotice}</p> : null}
                  {bulkImportNotice && bulkImportRole === 'STUDENT' ? <p className="user-management-notice" role="status">{bulkImportNotice}</p> : null}
                  {showBulkImport && bulkImportRole === 'STUDENT' ? (
                    <form className="academic-year-form" onSubmit={handleBulkImport}>
                      <div className="user-form-heading"><span className="eyebrow">CSV import</span><h3>Import student accounts</h3></div>
                      <p className="empty-note" style={{ marginBottom: 10 }}>Required columns: <code>username, password, first_name, last_name, admission_number</code>. Optional: <code>email, gender, parent_name</code></p>
                      {bulkImportError ? <p className="dashboard-error" role="alert">{bulkImportError}</p> : null}
                      <label className="form-field"><span>Paste CSV data</span><textarea className="bulk-import-textarea" required rows={8} value={bulkImportCsv} onChange={(e) => setBulkImportCsv(e.target.value)} placeholder={`username,password,first_name,last_name,admission_number,gender\nstudent1,Pass1234!,Alice,Smith,ADM001,Female`} /></label>
                      <div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isBulkImporting}>{isBulkImporting ? 'Importing...' : 'Import students'}</button><button className="ghost-btn" type="button" onClick={() => { setShowBulkImport(false); setBulkImportCsv(''); }}>Cancel</button></div>
                    </form>
                  ) : null}
                  {showBulkEnrollForm ? (
                    <form className="academic-year-form enrollment-form" onSubmit={handleBulkEnroll}>
                      <div className="user-form-heading"><span className="eyebrow">Bulk enrollment</span><h3>Enroll multiple students</h3></div>
                      {bulkEnrollError ? <p className="dashboard-error" role="alert">{bulkEnrollError}</p> : null}
                      <div className="academic-year-grid">
                        <label className="form-field"><span>Academic year</span><select required value={bulkEnrollContext.academic_year_id} onChange={(e) => setBulkEnrollContext({ ...bulkEnrollContext, academic_year_id: e.target.value, school_class_id: '', term_id: '' })}><option value="">Select year</option>{managedAcademicYears.map((y) => <option key={y.id} value={y.id}>{y.name}</option>)}</select></label>
                        <label className="form-field"><span>Class</span><select required value={bulkEnrollContext.school_class_id} onChange={(e) => setBulkEnrollContext({ ...bulkEnrollContext, school_class_id: e.target.value })}><option value="">Select class</option>{managedClasses.filter((c) => String(c.academic_year.id) === bulkEnrollContext.academic_year_id).map((c) => <option key={c.id} value={c.id}>{c.name}{c.section ? ` ${c.section}` : ''}</option>)}</select></label>
                        <label className="form-field"><span>Term</span><select required value={bulkEnrollContext.term_id} onChange={(e) => setBulkEnrollContext({ ...bulkEnrollContext, term_id: e.target.value })}><option value="">Select term</option>{managedTerms.filter((t) => String(t.academic_year.id) === bulkEnrollContext.academic_year_id).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
                      </div>
                      <p className="empty-note" style={{ marginBottom: 10 }}>Select students from the table below ({bulkEnrollIds.size} selected):</p>
                      <div className="table-scroll" style={{ maxHeight: 260, overflowY: 'auto', marginBottom: 12 }}>
                        <table><thead><tr><th><input type="checkbox" aria-label="Select all" checked={bulkEnrollIds.size === students.length && students.length > 0} onChange={(e) => setBulkEnrollIds(e.target.checked ? new Set(students.map((s) => s.id)) : new Set())} /></th><th>Admission</th><th>Name</th></tr></thead>
                          <tbody>{students.map((s) => <tr key={s.id}><td><input type="checkbox" checked={bulkEnrollIds.has(s.id)} onChange={(e) => setBulkEnrollIds((prev) => { const next = new Set(prev); e.target.checked ? next.add(s.id) : next.delete(s.id); return next; })} /></td><td>{s.admission_number}</td><td>{s.full_name}</td></tr>)}</tbody>
                        </table>
                      </div>
                      <div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isSavingBulkEnroll || !bulkEnrollIds.size}>{isSavingBulkEnroll ? 'Enrolling...' : `Enroll ${bulkEnrollIds.size || ''} student(s)`}</button><button className="ghost-btn" type="button" onClick={() => { setShowBulkEnrollForm(false); setBulkEnrollIds(new Set()); setBulkEnrollError(''); }}>Cancel</button></div>
                    </form>
                  ) : null}
                  {studentClassFilter ? <p className="roster-scope-note">Showing students enrolled in {teacherClasses.find((schoolClass) => String(schoolClass.id) === studentClassFilter)?.name || managedClasses.find((schoolClass) => String(schoolClass.id) === studentClassFilter)?.name || 'the selected class'}. <button type="button" className="text-btn" onClick={() => setStudentClassFilter('')}>View all students</button></p> : null}
                  {showEnrollmentForm ? <form className="academic-year-form enrollment-form" onSubmit={handleCreateEnrollment}>
                    <div className="user-form-heading"><span className="eyebrow">Class roster</span><h3>Enroll a student</h3></div>
                    {enrollmentOptionsError ? <p className="dashboard-error" role="alert">{enrollmentOptionsError}</p> : null}{enrollmentError ? <p className="dashboard-error" role="alert">{enrollmentError}</p> : null}
                    <div className="academic-year-grid">
                      <label className="form-field"><span>Student</span><select required value={enrollmentForm.student_id} onChange={(event) => setEnrollmentForm({ ...enrollmentForm, student_id: event.target.value })}><option value="">Select student</option>{students.map((student) => <option key={student.id} value={student.id}>{student.full_name} ({student.admission_number})</option>)}</select></label>
                      <label className="form-field"><span>Academic year</span><select required value={enrollmentForm.academic_year_id} onChange={(event) => setEnrollmentForm({ ...enrollmentForm, academic_year_id: event.target.value, school_class_id: '', term_id: '' })}><option value="">Select year</option>{managedAcademicYears.map((year) => <option key={year.id} value={year.id}>{year.name}</option>)}</select></label>
                      <label className="form-field"><span>Class</span><select required value={enrollmentForm.school_class_id} onChange={(event) => setEnrollmentForm({ ...enrollmentForm, school_class_id: event.target.value })}><option value="">Select class</option>{managedClasses.filter((schoolClass) => String(schoolClass.academic_year.id) === enrollmentForm.academic_year_id).map((schoolClass) => <option key={schoolClass.id} value={schoolClass.id}>{schoolClass.name}{schoolClass.section ? ` ${schoolClass.section}` : ''}</option>)}</select></label>
                      <label className="form-field"><span>Term</span><select required value={enrollmentForm.term_id} onChange={(event) => setEnrollmentForm({ ...enrollmentForm, term_id: event.target.value })}><option value="">Select term</option>{managedTerms.filter((term) => String(term.academic_year.id) === enrollmentForm.academic_year_id).map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}</select></label>
                    </div><div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isSavingEnrollment || !students.length}>{isSavingEnrollment ? 'Enrolling...' : 'Enroll student'}</button><button className="ghost-btn" type="button" onClick={() => { setShowEnrollmentForm(false); setEnrollmentError(''); }}>Cancel</button></div>
                  </form> : null}
                  {showDataManagementForm ? <form className="academic-year-form" onSubmit={handleSaveDataManagementRecord}>
                    <div className="user-form-heading"><span className="eyebrow">{editingDataRecordId ? 'Update student' : 'New student'}</span><h3>{editingDataRecordId ? 'Edit student profile' : 'Create student account'}</h3></div>
                    <div className="academic-year-grid">
                      {!editingDataRecordId ? <><label className="form-field"><span>Username</span><input required maxLength={150} autoComplete="username" value={dataManagementForm.username} onChange={(event) => setDataManagementForm({ ...dataManagementForm, username: event.target.value })} /></label><label className="form-field"><span>Initial password</span><input required type="password" minLength={8} autoComplete="new-password" value={dataManagementForm.password} onChange={(event) => setDataManagementForm({ ...dataManagementForm, password: event.target.value })} /></label></> : null}
                      <label className="form-field"><span>First name</span><input required maxLength={150} value={dataManagementForm.first_name} onChange={(event) => setDataManagementForm({ ...dataManagementForm, first_name: event.target.value })} /></label><label className="form-field"><span>Last name</span><input required maxLength={150} value={dataManagementForm.last_name} onChange={(event) => setDataManagementForm({ ...dataManagementForm, last_name: event.target.value })} /></label>
                      <label className="form-field"><span>Email</span><input type="email" value={dataManagementForm.email} onChange={(event) => setDataManagementForm({ ...dataManagementForm, email: event.target.value })} /></label><label className="form-field"><span>Phone number</span><input maxLength={20} value={dataManagementForm.phone_number} onChange={(event) => setDataManagementForm({ ...dataManagementForm, phone_number: event.target.value })} /></label>
                      <label className="form-field"><span>Admission number</span><input required maxLength={30} value={dataManagementForm.admission_number} onChange={(event) => setDataManagementForm({ ...dataManagementForm, admission_number: event.target.value })} /></label><label className="form-field"><span>Date of birth</span><input type="date" value={dataManagementForm.date_of_birth} onChange={(event) => setDataManagementForm({ ...dataManagementForm, date_of_birth: event.target.value })} /></label>
                      <label className="form-field"><span>Gender</span><select value={dataManagementForm.gender} onChange={(event) => setDataManagementForm({ ...dataManagementForm, gender: event.target.value })}><option value="">Select gender</option><option value="Female">Female</option><option value="Male">Male</option><option value="Other">Other</option></select></label>
                      <label className="form-field"><span>Current class (display)</span><input maxLength={50} value={dataManagementForm.current_class} onChange={(event) => setDataManagementForm({ ...dataManagementForm, current_class: event.target.value })} /></label>
                    </div><div className="user-form-actions"><button className="primary-btn" type="submit" disabled={isSavingDataManagement}>{isSavingDataManagement ? 'Saving...' : editingDataRecordId ? 'Save changes' : 'Create student'}</button><button className="ghost-btn" type="button" onClick={() => { setShowDataManagementForm(false); setEditingDataRecordId(null); setDataManagementError(''); }}>Cancel</button></div>
                  </form> : null}
                  <label className="form-field student-search"><span>Search students</span><input value={studentSearch} onChange={(event) => setStudentSearch(event.target.value)} placeholder="Name or admission number" /></label>
                  {isAdminWorkspace && (managedClasses.length === 0 || managedAcademicYears.length === 0 || managedTerms.length === 0) ? <p className="empty-note enrollment-prerequisite-note">Set up academic years, terms, and classes before enrolling students.</p> : null}
                  {isLoadingStudents ? <p className="empty-note">Loading students...</p> : null}
                  <table><thead><tr><th>Admission no.</th><th>Name</th><th>Class</th><th>Action</th>{isAdminWorkspace ? <th>Manage</th> : null}</tr></thead>
                    <tbody>{students.map((student) => <tr key={student.id}><td>{student.admission_number}</td><td>{student.full_name}</td><td>{studentClassFilter ? teacherClasses.find((schoolClass) => String(schoolClass.id) === studentClassFilter)?.name || managedClasses.find((schoolClass) => String(schoolClass.id) === studentClassFilter)?.name || student.current_class || '—' : student.current_class || '—'}</td><td><button className="text-btn" type="button" onClick={() => setSelectedStudent(student)}>Open profile</button></td>{isAdminWorkspace ? <td><div className="student-row-actions"><button className="text-btn" type="button" onClick={() => startDataManagementEdit(student)}>Edit</button><button className="text-btn" type="button" onClick={() => startStudentEnrollment(student)}>Enroll</button></div></td> : null}</tr>)}
                      {!students.length && !isLoadingStudents ? <tr><td colSpan={isAdminWorkspace ? 5 : 4} className="empty-table">{studentClassFilter ? 'No students are enrolled in this class yet. An administrator can enroll students from this page.' : user.role === 'TEACHER' ? 'No enrolled students are assigned to your classes yet.' : 'No students match this search.'}</td></tr> : null}
                    </tbody>
                  </table>
                </>
              ) : (
                <div className="student-profile" id={user.role !== 'STUDENT' || studentWorkspaceView === 'Result Slip' ? 'student-result-slip' : undefined}>
                  {user.role === 'STUDENT' && studentWorkspaceView === 'My Profile' ? (
                    <section className="student-workspace-card"><span className="eyebrow">Personal details</span><h2>{selectedStudent.full_name}</h2><div className="profile-facts"><p><strong>Admission number</strong><span>{selectedStudent.admission_number}</span></p><p><strong>Class</strong><span>{selectedStudent.current_class || '—'}</span></p><p><strong>Date of birth</strong><span>{selectedStudent.date_of_birth || '—'}</span></p><p><strong>Gender</strong><span>{selectedStudent.gender || '—'}</span></p><p><strong>Parent / guardian</strong><span>{selectedStudent.parent_name || '—'}</span></p><p><strong>Email</strong><span>{selectedStudent.user?.email || '—'}</span></p></div></section>
                  ) : user.role === 'STUDENT' && studentWorkspaceView === 'My Results' ? (
                    <section className="student-workspace-card"><div className="panel-header result-slip-header"><div><span className="eyebrow">Published results</span><h3>My results</h3></div><div className="result-slip-actions"><label>Academic year<select value={studentResultYearFilter} onChange={(event) => { setStudentResultYearFilter(event.target.value); setStudentResultTermFilter(''); }}><option value="">All years</option>{studentResultYears.map((year) => <option key={year.id} value={year.id}>{year.name}</option>)}</select></label><label>Term<select value={studentResultTermFilter} onChange={(event) => setStudentResultTermFilter(event.target.value)}><option value="">All terms</option>{studentResultTerms.map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}</select></label></div></div><div className="table-scroll">{studentResultsTable}</div></section>
                  ) : user.role === 'STUDENT' && studentWorkspaceView === 'My Performance' ? (
                    <section className="student-workspace-card"><div className="panel-header"><div><span className="eyebrow">Published assessment results</span><h3>My performance</h3></div></div><div className="result-slip-actions performance-filters"><label>Academic year<select value={studentResultYearFilter} onChange={(event) => { setStudentResultYearFilter(event.target.value); setStudentResultTermFilter(''); }}><option value="">All years</option>{studentResultYears.map((year) => <option key={year.id} value={year.id}>{year.name}</option>)}</select></label><label>Term<select value={studentResultTermFilter} onChange={(event) => setStudentResultTermFilter(event.target.value)}><option value="">All terms</option>{studentResultTerms.map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}</select></label></div><section className="stats-grid student-performance-stats"><article className="stat-card primary"><div><span>Overall average</span><strong>{studentOverallAverage.toFixed(1)}%</strong></div></article><article className="stat-card success"><div><span>Subjects with results</span><strong>{studentSubjectPerformance.length}</strong></div></article><article className="stat-card info"><div><span>Published marks</span><strong>{publishedStudentResults.length}</strong></div></article></section><div className="table-scroll"><table className="data-management-table"><thead><tr><th>Subject</th><th>Assessments</th><th>Average marks</th></tr></thead><tbody>{studentSubjectPerformance.map((subject) => <tr key={subject.name}><td>{subject.name}</td><td>{subject.count}</td><td>{subject.average.toFixed(1)}%</td></tr>)}{!studentSubjectPerformance.length ? <tr><td colSpan={3} className="empty-table">Published results will appear here when available.</td></tr> : null}</tbody></table></div></section>
                  ) : (
                    <div className="student-result-slip-content">
                      <div className="panel-header result-slip-header report-controls"><div><span className="eyebrow">Published results</span><h3>Student academic report</h3></div><div className="result-slip-actions"><label>Academic year<select value={studentResultYearFilter} onChange={(event) => { setStudentResultYearFilter(event.target.value); setStudentResultTermFilter(''); }}><option value="">Select year</option>{studentResultYears.map((year) => <option key={year.id} value={year.id}>{year.name}</option>)}</select></label><label>Term<select value={studentResultTermFilter} onChange={(event) => setStudentResultTermFilter(event.target.value)} disabled={!studentResultYearFilter}><option value="">Select term</option>{studentResultTerms.map((term) => <option key={term.id} value={term.id}>{term.name}</option>)}</select></label><button className="sign-in-btn print-btn" type="button" onClick={() => window.print()} disabled={!studentAcademicReport || isLoadingStudentReport}>Print / Save as PDF</button></div></div>
                      {studentReportError ? <p className="dashboard-error report-screen-message" role="alert">{studentReportError}</p> : null}
                      {isLoadingStudentReport ? <p className="empty-note report-screen-message">Preparing academic report...</p> : null}
                      {!studentResultYearFilter || !studentResultTermFilter ? <p className="empty-note report-screen-message">Select an academic year and term to view the student report.</p> : null}
                      {studentAcademicReport ? <>
                        <header className="academic-report-heading">{studentAcademicReport.school_name ? <span>{studentAcademicReport.school_name}</span> : null}<h2>Student Academic Report</h2><p>{studentAcademicReport.academic_year} | {formatTermName(studentAcademicReport.term)}</p></header>
                        <div className="academic-report-facts">
                          <p><strong>Student</strong><span>{studentAcademicReport.student.name}</span></p>
                          <p><strong>Student ID</strong><span>{studentAcademicReport.student.admission_number}</span></p>
                          <p><strong>Class</strong><span>{studentAcademicReport.student.class_name}</span></p>
                          <p><strong>Position</strong><span>{studentAcademicReport.position === null ? '—' : `${studentAcademicReport.position} / ${studentAcademicReport.class_size}`}</span></p>
                          <p><strong>Academic year</strong><span>{studentAcademicReport.academic_year}</span></p>
                          <p><strong>Term</strong><span>{formatTermName(studentAcademicReport.term)}</span></p>
                        </div>
                        <div className="table-scroll academic-report-table">
                          <table><thead><tr><th>Subject</th><th>Marks (%)</th><th>Grade</th><th>Remarks</th></tr></thead>
                            <tbody>
                              {studentAcademicReport.subjects.map((row) => <tr key={row.subject}><td>{row.subject}</td><td>{row.marks.toFixed(2).replace(/\.00$/, '')}</td><td><span className="grade-badge">{row.grade}</span></td><td>{row.remarks}</td></tr>)}
                              {!studentAcademicReport.subjects.length ? <tr><td colSpan={4} className="empty-table">No published results are available for this term.</td></tr> : null}
                            </tbody>
                          </table>
                        </div>
                        <div className="academic-report-summary">
                          <p><strong>Overall Average</strong><span>{studentAcademicReport.average === null ? '—' : `${studentAcademicReport.average}%`}</span></p>
                          <p><strong>Overall Grade</strong><span>{studentAcademicReport.overall_grade || '—'}</span></p>
                          <p><strong>Overall Status</strong><span className={`report-status-badge ${(studentAcademicReport.overall_status || '').toLowerCase()}`}>{studentAcademicReport.overall_status || '—'}</span></p>
                        </div>
                        <div className="academic-report-grading">
                          <span className="eyebrow">GRADING SCALE</span>
                          <table className="grading-table"><thead><tr><th>Grade</th><th>Range</th><th>Status</th></tr></thead>
                            <tbody>
                              {[['A','80 – 100','Excellent'],['B','70 – 79','Very Good'],['C','60 – 69','Good'],['D','50 – 59','Pass'],['F','0 – 49','Fail']].map(([g, r, s]) => (
                                <tr key={g} className={studentAcademicReport.overall_grade === g ? 'grading-row-active' : ''}><td><span className="grade-badge">{g}</span></td><td>{r}</td><td>{s}</td></tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        {(studentAcademicReport.approved_by || studentAcademicReport.published_by) ? (
                          <div className="academic-report-publication">
                            <span className="eyebrow">PUBLICATION DETAILS</span>
                            <div className="publication-grid">
                              <span className="report-status-badge published">PUBLISHED</span>
                              {studentAcademicReport.approved_by ? <p><strong>Approved by</strong><span>{studentAcademicReport.approved_by}{studentAcademicReport.approved_at ? ` · ${new Date(studentAcademicReport.approved_at).toLocaleDateString()}` : ''}</span></p> : null}
                              {studentAcademicReport.published_by ? <p><strong>Published by</strong><span>{studentAcademicReport.published_by}{studentAcademicReport.published_at ? ` · ${new Date(studentAcademicReport.published_at).toLocaleDateString()}` : ''}</span></p> : null}
                            </div>
                          </div>
                        ) : null}
                        <footer className="academic-report-signatures">
                          <p><span>{studentAcademicReport.class_teacher || ' '}</span><strong>Class Teacher</strong><small>Date: _______________</small></p>
                          <p><span>{studentAcademicReport.academic_officer || ' '}</span><strong>Academic Officer</strong><small>Date: _______________</small></p>
                        </footer>
                      </> : null}
                    </div>
                  )}
                </div>
              )}
            </section>
          </>
        ) : activeSection === 'Dashboard' && hasDashboard ? (
          <>
            {isLoadingDashboard ? <div className="loading-pill">Loading live records...</div> : null}
            {dashboardError ? <p className="dashboard-error" role="alert">{dashboardError}</p> : null}
            <section className="stats-grid">
              {statCards.map((stat) => (
                <button key={stat.label} type="button" className={`stat-card stat-card-button ${stat.color}`} onClick={() => {
                  setResultStatusFilter(stat.statusFilter || '');
                  if (user.role === 'TEACHER' && stat.section === 'Results') setTeacherResultsView('');
                  setNavigationSection(stat.section);
                }} aria-label={`View ${stat.label.toLowerCase()}`}>
                  <div><span>{stat.label}</span><strong>{stat.value}</strong></div><span className="stat-card-open" aria-hidden="true">View ›</span>
                </button>
              ))}
            </section>

            <section className="dashboard-quick-actions" aria-label="Quick actions">
              <div><span className="eyebrow">Quick actions</span><strong>Go to a common task</strong></div>
              <div className="dashboard-quick-action-list">
                {dashboardQuickActions.map((action) => <button key={action.label} type="button" onClick={() => {
                  setResultStatusFilter(action.statusFilter || '');
                  if (user.role === 'TEACHER') setTeacherResultsView('');
                  setNavigationSection(action.section);
                }}>{action.label}<span aria-hidden="true">→</span></button>)}
              </div>
            </section>

            <section className="panel dashboard-notifications" aria-label="Notifications">
              <div className="panel-header"><div><span className="eyebrow">For your account</span><h3>Notifications</h3></div><span className="notification-count">{dashboard.notifications.reduce((total, item) => total + item.count, 0)}</span></div>
              {dashboard.notifications.length ? (
                <ul className="notification-list">
                  {dashboard.notifications.map((notification) => (
                    <li key={`${notification.title}-${notification.status_filter}`}>
                      <span className="notification-badge">{notification.count}</span>
                      <div><strong>{notification.title}</strong><p>{notification.message}</p></div>
                      <button type="button" className="dashboard-panel-link" onClick={() => {
                        setResultStatusFilter(notification.status_filter);
                        if (user.role === 'TEACHER') setTeacherResultsView('');
                        setNavigationSection(notification.section);
                      }}>View <span aria-hidden="true">→</span></button>
                    </li>
                  ))}
                </ul>
              ) : <p className="empty-note">You have no pending notifications for this term.</p>}
            </section>

            {['SUPER_ADMIN', 'ADMIN', 'ACADEMIC_OFFICER'].includes(user.role) ? <section className={`dashboard-review-callout ${reviewQueueCount ? 'has-review-items' : ''}`}>
              <div><span className="eyebrow">Action required</span><strong>{reviewQueueCount ? `${reviewQueueCount} result${reviewQueueCount === 1 ? '' : 's'} waiting for review` : 'No results are waiting for review'}</strong><small>Submitted and under-review results for the active academic term.</small></div>
              <button type="button" onClick={() => { setResultStatusFilter('REVIEW_QUEUE'); setNavigationSection('Results'); }}>Open review queue <span aria-hidden="true">→</span></button>
            </section> : null}

            <section className="content-grid">
              <article className="panel panel-large">
                <div className="panel-header"><div><span className="eyebrow">{dashboard.academic_context.term ? `${dashboard.academic_context.academic_year} · ${dashboard.academic_context.term}` : 'Live results'}</span><h3>{user.role === 'STUDENT' ? 'My published results' : 'Result workflow'}</h3></div></div>
                <div className="result-status-chart" aria-label="Result counts by workflow status">
                  {visibleResultStatusBars.map((item) => (
                    <button key={item.label} type="button" className="result-status-row" onClick={() => {
                      setResultStatusFilter(item.label.toUpperCase().replace(/ /g, '_'));
                      setNavigationSection(user.role === 'STUDENT' ? 'My Results' : 'Results');
                    }} aria-label={`View ${item.count} ${item.label.toLowerCase()} results`}>
                      <span className="result-status-label">{item.label}<strong>{item.count}</strong></span>
                      <span className="result-status-track"><i className={`status-${item.label.toLowerCase().replace(/ /g, '-')}`} style={{ width: `${item.count ? Math.max((item.count / resultStatusMaximum) * 100, 2) : 0}%` }} /></span>
                    </button>
                  ))}
                </div>
              </article>
              <article className="panel panel-small">
                <div className="panel-header"><div><span className="eyebrow">Top performers</span><h3>Student leaders</h3></div><button type="button" className="dashboard-panel-link" onClick={() => setNavigationSection(user.role === 'STUDENT' ? 'My Performance' : 'Reports')}>View performance <span aria-hidden="true">→</span></button></div>
                {dashboard.top_students.length ? (
                  <ul className="leader-list">
                    {dashboard.top_students.map((student) => (
                      <li key={student.admission_number}>
                        <div><strong>{student.name}</strong><small>{student.admission_number}</small></div>
                        <span>{student.average.toFixed(1)}%</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="empty-note">No student results to display yet.</p>}
              </article>
            </section>

            <section className="panel table-panel">
              <div className="panel-header"><div><span className="eyebrow">Results</span><h3>Recent result entries</h3></div><button type="button" className="dashboard-panel-link" onClick={() => { setResultStatusFilter(''); if (user.role === 'TEACHER') setTeacherResultsView(''); setNavigationSection(user.role === 'STUDENT' ? 'My Results' : 'Results'); }}>View all results <span aria-hidden="true">→</span></button></div>
              <table>
                <thead><tr><th>Student</th><th>Subject</th><th>Term</th><th>Marks</th><th>Grade</th><th>Status</th></tr></thead>
                <tbody>
                  {dashboard.recent_results.map((result) => (
                    <tr key={result.id}>
                      <td>{result.student?.full_name || 'Student name'}</td>
                      <td>{result.subject?.name || 'Subject'}</td>
                      <td>{result.term?.name || 'Current term'}</td>
                      <td>{result.marks}</td>
                      <td><span className="grade-badge">{result.grade}</span></td>
                      <td><span className={`status-pill ${String(result.status).toLowerCase()}`}>{result.status}</span></td>
                    </tr>
                  ))}
                  {!dashboard.recent_results.length ? <tr><td colSpan={6} className="empty-table">No result entries yet. <button type="button" className="text-btn" onClick={() => setNavigationSection(user.role === 'TEACHER' ? 'Enter Results' : user.role === 'STUDENT' ? 'My Results' : 'Results')}>{user.role === 'TEACHER' ? 'Enter results' : user.role === 'STUDENT' ? 'View my results' : 'Open results workflow'}</button></td></tr> : null}
                </tbody>
              </table>
            </section>
          </>
        ) : isAdminWorkspace || user.role === 'STUDENT' ? null : (
          <section className="role-home panel">
            <div className="role-home-icon">{roleLabel.charAt(0)}</div>
            <span className="eyebrow">YOUR ROLE-BASED ACCESS</span>
            <h3>{roleLabel} workspace</h3>
            <p>Your account is signed in. Available areas are listed in the sidebar and are enforced by the server.</p>
            <div className="access-list">
              {roleAccess[user.role].map((item) => <span key={item}><span aria-hidden="true">✓</span>{item}</span>)}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
