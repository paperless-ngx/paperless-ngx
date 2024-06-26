import xml.etree.ElementTree as ET
from html import escape

# Paths to the uploaded files
messages_path = '/home/otxtan/project/tc-edoc/src-ui/messages.xlf'
messages_vi_path = '/home/otxtan/project/tc-edoc/src-ui/src/locale/messages.vi_VN.xlf'

tree_messages = ET.parse(messages_path)
root_messages = tree_messages.getroot()

tree_messages_vi = ET.parse(messages_vi_path)
root_messages_vi = tree_messages_vi.getroot()

namespace = {'ns': 'urn:oasis:names:tc:xliff:document:1.2'}
approvals_translations = {
    # "Approvals": "Phê duyệt",
    # "Approvals shows you documents that have been consumed, are waiting to be, or may have failure during the process.": "Phê duyệt cho bạn thấy các tài liệu đã được sử dụng, đang chờ được phê duyệt hoặc có thể có lỗi trong quá trình này.",
    # "Content type": "Loại nội dung",
    # "Submmit by": "Đệ trình bởi",
    # "Submmit by group": "Đệ trình bởi nhóm",
    # "Approve at": "Phê duyệt tại",
    # "Reject at": "Từ chối tại",
    # "Revoked at": "Đã huỷ tại",
    # "Method": "Phương thức",
    # "Approve": "Phê duyệt",
    # "Reject": "Từ chối",
    # "Revoked": "Đã huỷ",
    # "One": "Một",
    # "Failure": "Thất bại",
    # "Success": "Thành công",
    # "Pending": "Đang chờ",
    # "Revoked": "Đã huỷ",
    # "Approve selected": "Phê duyệt đã chọn",
    # "Approval all": "Phê duyệt tất cả",
    # "Reject selected": "Từ chối đã chọn",
    # "Reject all": "Từ chối tất cả",
    # "Revoke selected": "Huỷ đã chọn",
    # "Revoke all": "Huỷ tất cả",
    # "Confirm Approve All": "Xác nhận phê duyệt tất cả",
    # "Approve all": "Phê duyệt tất cả",
    # "Confirm Reject All": "Xác nhận từ chối tất cả",
    # "Reject all": "Từ chối tất cả",
    # "Confirm Revoke All": "Xác nhận huỷ tất cả",
    # "Revoke all": "Huỷ tất cả",
    # "Revoke": "Huỷ",
    # "pending": "Đang chờ",
    # "success": "Thành công",
    # "failure": "Thất bại",
    # "revoked": "Đã huỷ",
    # "Warehouses": "Kho",
    # "Approvals": "Phê duyệt",
    # "Access type": "Loại truy cập",
    # "Create exploitation request": "Tạo yêu cầu khai thác",
    # "Admin": "Quản trị",
    # "Access logs, Django backend": "Truy cập nhật ký, Django backend",
    # "Parent Warehouse": "Kho chính",
    # "Create new warehouse": "Tạo kho mới",
    # "Edit warehouse": "Chỉnh sửa kho",
    # "Has status": "Có trạng thái",
    # "Has content type": "Có loại nội dung",
    # "Has access type": "Có loại truy cập",
    # "Has groups": "Có nhóm",
    # "Assign to content type": "Gán cho loại nội dung",
    # "Approval Added": "Đã thêm phê duyệt",
    # "Approval Updated": "Đã cập nhật phê duyệt",
    # "Pending": "Đang chờ",
    # "Success": "Thành công",
    # "Failure": "Thất bại",
    # "Assignment with approval": "Gán với phê duyệt",
    # "Removal with approval": "Gỡ bỏ với phê duyệt",
    # "User": "Người dùng",
    # "Group": "Nhóm",
    # "Error saving approval": "Lỗi lưu phê duyệt",
    # "Error deleting approval": "Lỗi xóa phê duyệt",
    # "Warehouse": "Kho",
    # "Approvals": "Phê duyệt",
    # "Filter warehouses": "Lọc kho",
    # "Confirm warehouse assignment": "Xác nhận gán kho",
    # "This operation will assign the warehouse ": "Thao tác này sẽ gán kho ",
    # "This operation will remove the warehouse from ": "Thao tác này sẽ gỡ kho khỏi ",
    # "Mining requirements": "Yêu cầu khai thác",
    # "Filter by warehouse": "Lọc theo kho",
    # "Successfully sent mining request to ": "Đã gửi yêu cầu khai thác thành công đến ",
    # "Error saving field": "Lỗi lưu trường",
    # "Submitted mining request failed.": "Gửi yêu cầu khai thác thất bại.",
    # "Toggle warehouse filter": "Bật/tắt bộ lọc kho",
    # "Sort by warehouse": "Sắp xếp theo kho",
    # "Warehouse: ": "Kho: ",
    # "Without warehouse": "Không có kho",
    # "warehouse": "kho",
    # "warehouses": "kho",
    # "Do you really want to delete the warehouse ": "Bạn có thực sự muốn xóa kho "
}
# Hàm tìm phần tử <trans-unit> theo id trong tệp tiếng Việt
def find_trans_unit_by_id(trans_unit_id, vi_root):
    return vi_root.find(f".//ns:trans-unit[@id='{trans_unit_id}']", namespace)

# Duyệt qua từng <trans-unit> trong tệp gốc
for trans_unit in root_messages.findall(".//ns:trans-unit", namespace):
    trans_id = trans_unit.attrib.get("id")
    # print(trans_id)
    # Tìm phần tử <trans-unit> tương ứng trong tệp tiếng Việt
    trans_unit_vi = find_trans_unit_by_id(trans_id, root_messages_vi)
    
    if trans_unit_vi is not None:
        target_vi = trans_unit_vi.find("ns:target", namespace)
        
        if target_vi is not None and target_vi.text is not None:
            target = trans_unit.find("ns:target", namespace)
            
            if target is None:
                # Thêm phần tử target từ tệp tiếng Việt vào tệp gốc
                target = ET.SubElement(trans_unit, "{urn:oasis:names:tc:xliff:document:1.2}target", state="translated")
            target.text = ''.join(target_vi.itertext())
    elif trans_unit_vi is None:  
        target = ET.SubElement(trans_unit, "{urn:oasis:names:tc:xliff:document:1.2}target", state="needs-translation")
        # target.text = approvals_translations.get(trans_unit.find("ns:source", namespace).text)

        trans_unit_text = approvals_translations.get(trans_unit.find("ns:source", namespace).text) 
        target.text = ''.join(trans_unit.find("ns:source", namespace).itertext()) 
merged_file_path = '/home/otxtan/project/tc-edoc/src-ui/messages_merged.xlf'
tree_messages.write(merged_file_path)

print(f'Merged file saved to: {merged_file_path}')




