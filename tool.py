import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import re
from datetime import datetime
import copy

# Cấu hình trang hiển thị của Streamlit (Phải đặt ở dòng đầu tiên của code giao diện)
st.set_page_config(page_title="Phân Tích Dữ Liệu Tưới Tiêu", layout="wide")

# Bảng ánh xạ chỉ số hệ thống
MAP_CHI_SO = {
    'Tổng thời gian tưới (Phút)': 'phut',
    'TBEC Thực tế': 'tbec',
    'EC Yêu cầu': 'ec_yc'
}

# ==========================================
# 1. HÀM XỬ LÝ ĐỌC FILE JSON BỊ LỖI CÚ PHÁP
# ==========================================
def json_decode_helper(chuoi_raw):
    # Loại bỏ các ký tự khoảng trắng ẩn đặc biệt dễ gây treo hoặc lỗi giải mã
    noi_dung = chuoi_raw.replace('\xa0', ' ').strip()
    
    # Sửa lỗi file JSON dạng các object viết liền nhau: } { -> },{
    noi_dung = re.sub(r'}\s*{', '},{', noi_dung)
    
    # Nếu chưa bọc trong mảng vuông [] thì bọc lại cho đúng chuẩn JSON Array
    if not noi_dung.startswith('['):
        noi_dung = '[' + noi_dung
    if not noi_dung.endswith(']'):
        noi_dung = noi_dung + ']'
        
    try:
        return json.loads(noi_dung)
    except json.JSONDecodeError:
        # Nếu vẫn lỗi, thử parse thủ công từng dòng object
        danh_sach_obj = []
        # Tìm tất cả các đoạn nội dung nằm giữa dấu { và }
        matches = re.findall(r'\{.*?\}', noi_dung, re.DOTALL)
        for m in matches:
            try:
                danh_sach_obj.append(json.loads(m))
            except:
                continue
        return danh_sach_obj

# ==========================================
# 2. HÀM CHUẨN BỊ VÀ ĐỒNG BỘ DỮ LIỆU THÔ
# ==========================================
def chuan_bi_du_lieu_tho(bytes_nhat_ky, bytes_chi_phi, stt_khu_chon):
    try:
        raw_nk = bytes_nhat_ky.decode('utf-8-sig')
        raw_cp = bytes_chi_phi.decode('utf-8-sig')
    except:
        raw_nk = bytes_nhat_ky.decode('latin-1')
        raw_cp = bytes_chi_phi.decode('latin-1')

    ds_nhat_ky = json_decode_helper(raw_nk)
    ds_chi_phi = json_decode_helper(raw_cp)

    # Lọc dữ liệu theo Khu được chọn
    khu_str = f"Khu {stt_khu_chon}"
    nk_loc = [d for d in ds_chi_phi if d.get('ten_khu') == khu_str]
    cp_loc = [d for d in ds_nhat_ky if d.get('ten_khu') == khu_str]

    if not nk_loc:
        return []

    # Gom nhóm dữ liệu nhật ký theo từng Vụ canh tác
    du_lieu_vụ_Gom = {}
    for item in nk_loc:
        stt_vu = item.get('stt_vu')
        if stt_vu is None:
            continue
        if stt_vu not in du_lieu_vụ_Gom:
            du_lieu_vụ_Gom[stt_vu] = []
        du_lieu_vụ_Gom[stt_vu].append(item)

    # Trộn thêm thông tin EC Yêu Cầu từ file chi phí sang file nhật ký theo đúng Ngày
    dict_ec_yc = {}
    for item in cp_loc:
        ngay_str = item.get('ngay_hien_tai', '').split(' ')[0]
        ec_val = item.get('ec_dat_cai', 0.0)
        if ngay_str:
            dict_ec_yc[ngay_str] = float(ec_val)

    danh_sach_cac_vu_hoan_thien = []
    cac_vu_sap_xep = sorted(list(du_lieu_vụ_Gom.keys()))

    for vu in cac_vu_sap_xep:
        data_nk_vu = du_lieu_vụ_Gom[vu]
        data_vu_da_xu_ly = []
        
        for item in data_nk_vu:
            ngay_str = item.get('ngay_hien_tai', '').split(' ')[0]
            if not ngay_str:
                continue
                
            try:
                ngay_dt = datetime.strptime(ngay_str, '%Y-%m-%d')
            except:
                continue

            ec_yc_val = dict_ec_yc.get(ngay_str, 0.0)
            
            data_vu_da_xu_ly.append({
                'ngay': ngay_dt,
                'nhan_ngay': ngay_dt.strftime('%d/%m'),
                'so_lan': int(item.get('so_lan_tuoi', 0)),
                'phut': float(item.get('tong_so_phut_tuoi', 0.0)),
                'tbec': float(item.get('tbec_thuc_te', 0.0)),
                'tbph': float(item.get('tbph_thuc_te', 0.0)),
                'ec_yc': ec_yc_val,
                'giai_doan': 1  # Mặc định ban đầu là giai đoạn 1
            })
            
        if data_vu_da_xu_ly:
            # Sắp xếp lịch sử canh tác tăng dần theo dòng thời gian
            data_vu_da_xu_ly.sort(key=lambda x: x['ngay'])
            danh_sach_cac_vu_hoan_thien.append(data_vu_da_xu_ly)

    return danh_sach_cac_vu_hoan_thien

# ==========================================
# 3. THUẬT TOÁN TÍNH TOÁN CHIA GIAI ĐOẠN ĐỘNG
# ==========================================
def tinh_toan_giai_doan_dong(du_lieu_vu, danh_sach_khoa, dict_sai_so):
    if not du_lieu_vu:
        return []
        
    giai_doan_hien_tai = 1
    du_lieu_vu[0]['giai_doan'] = giai_doan_hien_tai
    
    # Lấy giá trị nền móng của ngày đầu tiên làm mốc so sánh
    goc_so_sanh = {khoa: du_lieu_vu[0][khoa] for khoa in danh_sach_khoa}

    for idx in range(1, len(du_lieu_vu)):
        ngay_tiep_theo = du_lieu_vu[idx]
        thay_doi_vuot_nguong = False

        # Kiểm tra xem có chỉ số nào vượt quá biên độ sai số cài đặt hay không (Điều kiện AND)
        for khoa in danh_sach_khoa:
            gia_tri_goc = goc_so_sanh[khoa]
            gia_tri_moi = ngay_tiep_theo[khoa]
            sai_so_cho_phep = dict_sai_so.get(khoa, 0.5)

            if abs(gia_tri_moi - gia_tri_goc) > sai_so_cho_phep:
                thay_doi_vuot_nguong = True
                break # Chỉ cần 1 chỉ số vượt ngưỡng là kích hoạt đổi giai đoạn

        if thay_doi_vuot_nguong:
            giai_doan_hien_tai += 1
            # Cập nhật lại mốc so sánh mới chính là ngày bước sang giai đoạn mới này
            goc_so_sanh = {khoa: ngay_tiep_theo[khoa] for khoa in danh_sach_khoa}

        ngay_tiep_theo['giai_doan'] = giai_doan_hien_tai

    return du_lieu_vu

# ==========================================
# 4. GIAI ĐOẠN HIỂN THỊ ĐỒ THỊ & BẢNG SỐ LIỆU (TỐI ƯU TỐC ĐỘ)
# ==========================================
def xuat_bao_cao_streamlit(du_lieu_vu, stt_vu, danh_sach_ten_chi_so_chon):
    so_ngay = len(du_lieu_vu)
    if so_ngay == 0:
        st.warning(f"Không có dữ liệu cho Vụ {stt_vu}")
        return

    ngay_dau, ngay_cuoi = du_lieu_vu[0]['ngay'], du_lieu_vu[-1]['ngay']
    
    khoa_chi_so_input = MAP_CHI_SO[danh_sach_ten_chi_so_chon[0]] if danh_sach_ten_chi_so_chon else 'phut'
    ten_chi_so_hien_thi_chinh = danh_sach_ten_chi_so_chon[0] if danh_sach_ten_chi_so_chon else 'Tổng thời gian tưới (Phút)'

    st.markdown(f"### VỤ {stt_vu}: {ngay_dau.strftime('%d/%m/%Y')} ➔ {ngay_cuoi.strftime('%d/%m/%Y')} ({so_ngay} ngày)")
    
    nhan = [d['nhan_ngay'] for d in du_lieu_vu]
    ds_phut = [d['phut'] for d in du_lieu_vu]
    ds_tbec = [d['tbec'] if d['tbec'] > 0 else None for d in du_lieu_vu]
    ds_ec_yc = [d['ec_yc'] if d['ec_yc'] > 0 else None for d in du_lieu_vu]
    ds_giai_doan = [d['giai_doan'] for d in du_lieu_vu]

    # Khung chỉ số tổng quan (Metrics)
    tong_phut = sum(ds_phut)
    cac_tbec_hop_le = [x for x in ds_tbec if x is not None]
    tb_ec = sum(cac_tbec_hop_le) / len(cac_tbec_hop_le) if cac_tbec_hop_le else 0.0
    giai_doan_cuoi = ds_giai_doan[-1] if ds_giai_doan else 1

    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Tổng Thời Gian Tưới", f"{tong_phut:,.0f} phút")
        col2.metric("EC Trung Bình", f"{tb_ec:.2f}")
        col3.metric("Giai Đoạn Hiện Tại", f"GĐ {giai_doan_cuoi}")
        col4.metric("Số Ngày Canh Tác", f"{so_ngay} ngày")
    
    st.markdown("<br>", unsafe_allow_html=True)

    # VẼ BIỂU ĐỒ TOÀN VỤ
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.08,
        row_heights=[0.60, 0.40], 
        subplot_titles=("<b>Biến động Thời Gian Tưới & EC (Toàn vụ)</b>", f"<b>Phân tách GĐ (Biểu đồ hiển thị: {ten_chi_so_hien_thi_chinh})</b>"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    fig.add_trace(go.Bar(x=nhan, y=ds_phut, name='Thời gian tưới (Phút)', marker_color='#aed6f1', opacity=0.75), row=1, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=nhan, y=ds_tbec, name='TBEC Thực', mode='lines', line=dict(color='#e74c3c', width=3)), row=1, col=1, secondary_y=True)
    fig.add_trace(go.Scatter(x=nhan, y=ds_ec_yc, name='EC Yêu Cầu', mode='lines', line=dict(color='#9b59b6', width=2.5, dash='dot')), row=1, col=1, secondary_y=True)

    giai_doan_duy_nhat = sorted(list(set(ds_giai_doan)))
    mau_sac_gd = ['#3498db', '#2ecc71', '#f1c40f', '#e67e22', '#9b59b6', '#34495e', '#1abc9c', '#e74c3c']
    
    for i, gd in enumerate(giai_doan_duy_nhat):
        x_gd = [d['nhan_ngay'] for d in du_lieu_vu if d['giai_doan'] == gd]
        y_gd = [d[khoa_chi_so_input] for d in du_lieu_vu if d['giai_doan'] == gd] 
        fig.add_trace(go.Bar(x=x_gd, y=y_gd, name=f'GĐ {gd} : {len(x_gd)} ngày', marker_color=mau_sac_gd[i % len(mau_sac_gd)]), row=2, col=1)

    fig.update_layout(height=800, template="plotly_white", hovermode="x unified", margin=dict(l=30, r=30, t=60, b=20), barmode='group')
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    # PHẦN XEM CHI TIẾT TỪNG GIAI ĐOẠN
    st.markdown("#### TỔNG KẾT CHI TIẾT THEO GIAI ĐOẠN")
    chon_gd = st.radio(f"Chọn Giai đoạn của Vụ {stt_vu} để xem chi tiết:", options=giai_doan_duy_nhat, format_func=lambda x: f"Giai đoạn {x}", key=f"chon_gd_vu_{stt_vu}", horizontal=True)

    data_gd = [d for d in du_lieu_vu if d['giai_doan'] == chon_gd]
    
    if data_gd:
        # Biểu đồ thu nhỏ cho giai đoạn được chọn
        x_gd_chart = [d['nhan_ngay'] for d in data_gd]
        y_phut_gd = [d['phut'] for d in data_gd]
        y_tbec_gd = [d['tbec'] if d['tbec'] > 0 else None for d in data_gd]
        y_ec_yc_gd = [d['ec_yc'] if d['ec_yc'] > 0 else None for d in data_gd]

        fig_gd = make_subplots(specs=[[{"secondary_y": True}]])
        fig_gd.add_trace(go.Bar(x=x_gd_chart, y=y_phut_gd, name='Thời gian tưới (Phút)', marker_color='#aed6f1', opacity=0.8), secondary_y=False)
        fig_gd.add_trace(go.Scatter(x=x_gd_chart, y=y_tbec_gd, name='TBEC Thực', mode='lines+markers', line=dict(color='#e74c3c', width=2)), secondary_y=True)
        fig_gd.add_trace(go.Scatter(x=x_gd_chart, y=y_ec_yc_gd, name='EC Yêu Cầu', mode='lines+markers', line=dict(color='#9b59b6', width=2, dash='dot')), secondary_y=True)
        fig_gd.update_layout(title=f"<b>Biểu đồ thông số chi tiết - Giai đoạn {chon_gd}</b>", height=350, template="plotly_white", hovermode="x unified", margin=dict(l=20, r=20, t=50, b=10))
        st.plotly_chart(fig_gd, use_container_width=True, config={'displayModeBar': False})

        # Dựng bảng số liệu Pandas DataFrame
        df_gd = pd.DataFrame(data_gd)
        df_gd = df_gd[['ngay', 'nhan_ngay', 'so_lan', 'phut', 'tbec', 'tbph', 'ec_yc', 'giai_doan']]
        df_gd.rename(columns={'ngay': 'Ngày', 'nhan_ngay': 'Nhãn Ngày', 'so_lan': 'Số Lần Tưới', 'phut': 'Số Phút', 'tbec': 'TBEC Thực', 'tbph': 'TBpH', 'ec_yc': 'EC Yêu Cầu', 'giai_doan': 'Giai Đoạn'}, inplace=True)

        so_ngay_gd = len(df_gd)
        df_summary = pd.DataFrame([{
            'Ngày': 'TRUNG BÌNH/TỔNG', 'Nhãn Ngày': f'{so_ngay_gd} ngày',
            'Số Lần Tưới': round(df_gd['Số Lần Tưới'].mean(), 1), 'Số Phút': round(df_gd['Số Phút'].mean(), 1),
            'TBEC Thực': round(df_gd['TBEC Thực'].mean(), 2), 'TBpH': round(df_gd['TBpH'].mean(), 2),
            'EC Yêu Cầu': round(df_gd['EC Yêu Cầu'].mean(), 2), 'Giai Đoạn': chon_gd
        }])
        df_hien_thi = pd.concat([df_gd, df_summary], ignore_index=True)

        # Định vị danh sách cột cần tô sáng dựa vào nút chọn bên trái của user
        map_cot_hien_thi = {'Tổng thời gian tưới (Phút)': 'Số Phút', 'TBEC Thực tế': 'TBEC Thực', 'EC Yêu cầu': 'EC Yêu Cầu'}
        danh_sach_cot_to_dam = [map_cot_hien_thi[ten] for ten in danh_sach_ten_chi_so_chon if ten in map_cot_hien_thi]

        # =========================================================
        # THUẬT TOÁN HIGHLIGHT MA TRẬN TỐC ĐỘ CAO (KHÔNG GÂY TREO APP)
        # =========================================================
        def highlight_table(df):
            df_style = pd.DataFrame('', index=df.index, columns=df.columns)
            
            # Tô màu nền đậm cho toàn bộ dòng tổng kết cuối cùng
            css_dong_cuoi = 'font-weight: bold; background-color: #ecf0f1; color: #2c3e50; font-size: 16px !important;'
            df_style.iloc[-1, :] = css_dong_cuoi
            
            css_cot_highlight = 'font-weight: bold; color: #d35400; background-color: #fef9e7;'
            css_giao_cat = 'font-weight: bold; background-color: #ecf0f1; color: #d35400; font-size: 16px !important;'
            
            # Cắt lát ma trận để nhuộm màu nguyên cột (Vectorization) - triệt tiêu lỗi treo CPU
            for cot in danh_sach_cot_to_dam:
                if cot in df_style.columns:
                    col_idx = df_style.columns.get_loc(cot)
                    df_style.iloc[:-1, col_idx] = css_cot_highlight
                    df_style.iloc[-1, col_idx] = css_giao_cat
                    
            return df_style

        format_mapping = {
            'Số Lần Tưới': lambda x: f"{x:g}" if isinstance(x, (int, float)) else x,
            'Số Phút': lambda x: f"{x:g}" if isinstance(x, (int, float)) else x,
            'TBEC Thực': lambda x: f"{x:g}" if isinstance(x, (int, float)) else x,
            'TBpH': lambda x: f"{x:g}" if isinstance(x, (int, float)) else x,
            'EC Yêu Cầu': lambda x: f"{x:g}" if isinstance(x, (int, float)) else x
        }

        chi_so_chuoi = " + ".join(danh_sach_cot_to_dam) if danh_sach_cot_to_dam else "Không"
        st.caption(f"Chi tiết lịch sử tưới trong **Giai đoạn {chon_gd}** (Cột **{chi_so_chuoi}** đang được bôi sáng):")
        st.dataframe(df_hien_thi.style.format(format_mapping).apply(highlight_table, axis=None), use_container_width=True, hide_index=True)

# ==========================================
# 5. KHUNG ĐIỀU HƯỚNG GIAO DIỆN CHÍNH (MAIN APP)
# ==========================================
st.sidebar.header("⚙️ CẤU HÌNH HỆ THỐNG")

stt_khu = st.sidebar.text_input("Nhập Số Thứ Tự Khu (Ví dụ: 1, 2...):", value="1")

file_ng = st.sidebar.file_uploader("1. Tải lên file Nhật Ký (.json)", type=["json"])
file_cp = st.sidebar.file_uploader("2. Tải lên file Chi Phí (.json)", type=["json"])

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 TIÊU CHÍ PHÂN CHIA GIAI ĐOẠN")

ten_chi_so_chon = st.sidebar.multiselect(
    "Chọn chỉ số kích hoạt phân tách (Điều kiện AND):",
    options=['Tổng thời gian tưới (Phút)', 'TBEC Thực tế', 'EC Yêu cầu'],
    default=['Tổng thời gian tưới (Phút)']
)

# Khởi tạo các khung nhập sai số tương ứng với chỉ số được tích chọn
dict_sai_so_cai_dat = {}
danh_sach_khoa_tinh_toan = []

if 'Tổng thời gian tưới (Phút)' in ten_chi_so_chon:
    dict_sai_so_cai_dat['phut'] = st.sidebar.number_input("Sai số Số Phút Tưới cho phép:", value=15.0, step=1.0)
    danh_sach_khoa_tinh_toan.append('phut')

if 'TBEC Thực tế' in ten_chi_so_chon:
    dict_sai_so_cai_dat['tbec'] = st.sidebar.number_input("Sai số chỉ số TBEC cho phép:", value=0.3, step=0.05)
    danh_sach_khoa_tinh_toan.append('tbec')

if 'EC Yêu cầu' in ten_chi_so_chon:
    dict_sai_so_cai_dat['ec_yc'] = st.sidebar.number_input("Sai số chỉ số EC Yêu Cầu cho phép:", value=0.2, step=0.05)
    danh_sach_khoa_tinh_toan.append('ec_yc')

# Quản lý trạng thái bấm nút Chạy của người dùng qua session_state
if 'da_bat_dau' not in st.session_state:
    st.session_state['da_bat_dau'] = False

st.sidebar.markdown("<br>", unsafe_allow_html=True)
if st.sidebar.button("📊 XUẤT BÁO CÁO TOÀN DIỆN", use_container_width=True, type="primary"):
    st.session_state['da_bat_dau'] = True

# LOGIC ĐIỀU HƯỚNG HIỂN THỊ CHÍNH TRÊN MÀN HÌNH
st.title("🌱 HỆ THỐNG PHÂN TÍCH DỮ LIỆU TƯỚI TIÊU NÂNG CAO")
st.subheader("Phân tách giai đoạn động tự động theo thuật toán ma trận biên độ")

if st.session_state['da_bat_dau']:
    if not ten_chi_so_chon:
        st.error("Lỗi cấu hình: Bạn phải chọn ít nhất 1 chỉ số ở thanh bên trái để làm căn cứ thuật toán phân chia giai đoạn.")
    elif file_ng and file_cp:
        # Bước 1: Gọi hàm đọc và chuẩn hóa dữ liệu thô từ file JSON
        du_lieu_cac_vu_tho = chuan_bi_du_lieu_tho(file_ng.getvalue(), file_cp.getvalue(), stt_khu)
        
        if not du_lieu_cac_vu_tho:
            st.error(f"Hệ thống không tìm thấy bất kỳ bản ghi dữ liệu hợp lệ nào tương ứng với 'Khu {stt_khu}' trong file của bạn.")
        else:
            # Tạo thanh chuyển đổi nhanh giữa các Vụ được tìm thấy trong file dữ liệu
            so_luong_vu = len(du_lieu_cac_vu_tho)
            danh_sach_nhan_vu = [f"Xem Vụ {i+1}" for i in range(so_luong_vu)]
            
            che_do_xem = st.selectbox("🔄 Chọn vụ canh tác muốn kiểm tra cấu trúc dữ liệu:", options=danh_sach_nhan_vu)
            
            # Lấy vị trí vụ được chọn
            stt_vu_chon = danh_sach_nhan_vu.index(che_do_xem) + 1
            data_vu_chọn = copy.deepcopy(du_lieu_cac_vu_tho[stt_vu_chon - 1])
            
            # Bước 2: Kích hoạt thuật toán ma trận động tính toán phân chia giai đoạn
            ket_qua_giai_doan = tinh_toan_giai_doan_dong(data_vu_chọn, danh_sach_khoa_tinh_toan, dict_sai_so_cai_dat)
            
            # Bước 3: Đưa kết quả ra hàm hiển thị giao diện đồ thị, bảng biểu
            xuat_bao_cao_streamlit(ket_qua_giai_doan, stt_vu_chon, ten_chi_so_chon)
    else:
        st.warning("⚠️ Vui lòng tải đầy đủ cả 2 file: File Nhật Ký (.json) và File Chi Phí (.json) ở cột bên trái để hệ thống đồng bộ số liệu.")
else:
    # Giao diện chào mừng mặc định khi user chưa tải file lên
    st.info("👋 Chào mừng bạn đến với hệ thống phân tích! Hãy tiến hành tải 2 file dữ liệu JSON ở thanh menu bên trái, thiết lập biên độ sai số của thuật toán, sau đó bấm nút **XUẤT BÁO CÁO TOÀN DIỆN** để bắt đầu phân tích lịch sử tưới tiêu.")