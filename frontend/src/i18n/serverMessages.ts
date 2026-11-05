import english from './en.json';
import { getStoredLocale } from './I18nProvider';
import { translate, type Locale } from './translate';

const known: Record<string, string> = english;
const englishToVietnamese: Record<string, string> = {
  'Admin role required for this endpoint': 'Chỉ quản trị viên mới có quyền truy cập.',
  'Application not found': 'Không tìm thấy hồ sơ ứng viên.',
  'Authentication required': 'Vui lòng đăng nhập.',
  'Authentication service is not configured': 'Dịch vụ xác thực chưa được cấu hình.',
  'Authentication verification is not configured': 'Xác minh đăng nhập chưa được cấu hình.',
  'Could not generate file access URL': 'Không thể tạo liên kết xem tệp.',
  'Could not validate credentials': 'Không thể xác thực thông tin đăng nhập.',
  'Invalid file location': 'Vị trí tệp không hợp lệ.',
  'Invalid file path': 'Đường dẫn tệp không hợp lệ.',
  'Invalid position id': 'Mã vị trí không hợp lệ.',
  'Invalid user credentials': 'Thông tin đăng nhập không hợp lệ.',
  'Required role is not assigned': 'Tài khoản chưa được phân công vai trò cần thiết.',
  'Storage backend is not configured': 'Dịch vụ lưu trữ chưa được cấu hình.',
  'Supabase storage is not configured': 'Kho lưu trữ Supabase chưa được cấu hình.',
  'You do not have permission to access this position': 'Bạn không có quyền truy cập vị trí này.',
  'Cannot run assessment: criteria have not been approved by HR and Hiring Manager': 'Tiêu chí cần được HR và Hiring Manager duyệt trước khi đánh giá.',
  'External AI endpoints are disabled by configuration': 'Cấu hình không cho phép endpoint AI bên ngoài.',
  'External AI endpoints require HTTPS': 'Endpoint AI bên ngoài phải dùng HTTPS.',
  'Position not found': 'Không tìm thấy vị trí.',
  'Operation not found': 'Không tìm thấy tác vụ.',
  'LLM_API_BASE is not configured': 'Chưa cấu hình endpoint AI.',
  'Invalid LLM API endpoint': 'Endpoint AI không hợp lệ.',
};

export function localizeServerMessage(message: unknown, locale: Locale = getStoredLocale()): string {
  if (typeof message !== 'string') return translate('Dữ liệu gửi đi không hợp lệ.', locale);
  if (locale === 'vi') {
    if (englishToVietnamese[message]) return englishToVietnamese[message];
    if (known[message] || /[À-ỹĐđ]/.test(message)) return message;
    return translate('Không thể hoàn tất yêu cầu. Vui lòng thử lại.', locale);
  }
  if (known[message]) return known[message];
  if (englishToVietnamese[message] || Object.values(known).includes(message)) return message;
  // Avoid displaying untranslated or potentially sensitive server exceptions.
  return translate('Không thể hoàn tất yêu cầu. Vui lòng thử lại.', locale);
}
