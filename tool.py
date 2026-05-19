import json
import re
import copy
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# CÁC HẰNG SỐ CỐ ĐỊNH HỆ THỐNG
# ==========================================
SO_NGAY_TOI_THIEU_VU = 15
NGUONG_GIAY_TUOI = 20
NGUONG_CHIA_SO = 10.0
TY_LE_CHIA = 100.0

MAP_CHI_SO = {
    'Tổng thời gian tưới (Phút)': 'phut',
    'TBEC Thực tế': 'tbec',
    'EC Yêu cầu': 'ec_yc'
}

# ==========================================
# KHỐI XỬ LÝ LÕI & CACHE
# ==========================================
def json_decode_helper(file_bytes):
    try:
        noi_dung = file_bytes.decode("utf-8").strip()
        if not noi_dung: return []
        noi_dung = re.sub(r'}\s*{', '},{', noi_dung)
        if not noi_dung.startswith('['): noi_dung = f"[{noi_dung}]"
        noi_dung = re.sub(r',\s*]', ']', noi_dung)
        return json.loads(noi_dung)
    except Exception:
        return []

def chuan_hoa_so_thuc(gia_tri):
    if gia_tri is None or str(gia_tri).strip() == '': return 0.0
    try:
        so = float(gia_tri)
        return so / TY_LE_CHIA if so > NGUONG_CHIA_SO else so
    except ValueError:
        return 0.0

def lay_gia_tri_linh_hoat(dong, danh_sach_tu_khoa):
    for key, val in dong.items():
        if str(key).strip().lower() in danh_sach_tu_khoa:
            return val
    return None

def lay_du_lieu_ec_yeu_cau(du_lieu, stt_khu):
    ket_qua = {}
    stt_khu_chuan = str(stt_khu).strip().replace('.0', '')
    for dong in du_lieu:
        stt_dong = str(dong.get("STT", "")).strip().replace('.0', '')
        if stt_dong == stt_khu_chuan:
            tg_tho = lay_gia_tri_linh_hoat(dong, ['thời gian', 'thoi gian', 'thoi_gian'])
            ec = chuan_hoa_so_thuc(lay_gia_tri_linh_hoat(dong, ['ec yêu cầu', 'ec yeu cau', 'ec_yeu_cau']))
            if tg_tho and ec > 0:
                try:
                    tg_clean = str(tg_tho).split('.')[0].replace(':', '-')
                    ngay = datetime.strptime(tg_clean, "%Y-%m-%d %H-%M-%S").date()
                    if ngay not in ket_qua: ket_qua[ngay] = []
                    ket_qua[ngay].append(ec)
                except: pass
    return {n: round(sum(v)/len(v), 2) for n, v in ket_qua.items()}

@st.cache_data(show_spinner="Đang xử lý và bóc tách dữ liệu thô (Chỉ chạy 1 lần duy nhất)...")
def chuan_bi_du_lieu_tho(ng_bytes, cp_bytes, stt_khu):
    du_lieu_ng = json_decode_helper(ng_bytes)
    du_lieu_cp = json_decode_helper(cp_bytes)
    
    dict_ec_yc = lay_du_lieu_ec_yeu_cau(du_lieu_cp, stt_khu)
    ds_ban_ghi = []
    tap_ngay = set()
    stt_khu_chuan = str(stt_khu).strip().replace('.0', '')
    
    for dong in du_lieu_ng:
        stt_dong = str(dong.get("STT", "")).strip().replace('.0', '')
        if stt_dong == stt_khu_chuan:
            tg_tho = lay_gia_tri_linh_hoat(dong, ['thời gian', 'thoi gian', 'thoi_gian'])
            if tg_tho:
                try:
                    tg_clean = str(tg_tho).split('.')[0].replace(':', '-')
                    dt_obj = datetime.strptime(tg_clean, "%Y-%m-%d %H-%M-%S")
                    tap_ngay.add(dt_obj.date())
                    ds_ban_ghi.append({
                        'dt': dt_obj, 'ngay': dt_obj.date(),
                        'trang_thai': str(lay_gia_tri_linh_hoat(dong, ['trạng thái', 'trang thai'])).lower(),
                        'tbec': chuan_hoa_so_thuc(lay_gia_tri_linh_hoat(dong, ['tbec'])),
                        'tbph': chuan_hoa_so_thuc(lay_gia_tri_linh_hoat(dong, ['tbph']))
                    })
                except: pass
                
    if not tap_ngay: return []
    
    ds_ngay = sorted(list(tap_ngay))
    cac_vu = []
    vu_tam = [ds_ngay[0]]
    for i in range(1, len(ds_ngay)):
        if (ds_ngay[i] - ds_ngay[i-1]).days == 1:
            vu_tam.append(ds_ngay[i])
        else:
            cac_vu.append(vu_tam); vu_tam = [ds_ngay[i]]
    cac_vu.append(vu_tam)
    
    ds_ban_ghi.sort(key=lambda x: x['dt'])
    du_lieu_tong_hop = []
    
    for vu in cac_vu:
        if len(vu) < SO_NGAY_TOI_THIEU_VU: continue
        
        ket_qua_ngay_tho = []
        for thu_tu, ngay in enumerate(vu, 1):
            dong_trong_ngay = [r for r in ds_ban_ghi if r['ngay'] == ngay]
            giay_tong, so_lan, moc_bat = None, 0, None
            
            for r in dong_trong_ngay:
                if r['trang_thai'] == 'bật': moc_bat = r['dt']
                elif r['trang_thai'] == 'tắt' and moc_bat:
                    giay = (r['dt'] - moc_bat).total_seconds()
                    if giay > NGUONG_GIAY_TUOI:
                        giay_tong = (giay_tong or 0) + giay
                        so_lan += 1
                    moc_bat = None
            
            ds_ec = [r['tbec'] for r in dong_trong_ngay if r['tbec'] > 0]
            ds_ph = [r['tbph'] for r in dong_trong_ngay if r['tbph'] > 0]
            
            # Khắc phục lỗi chia cho 0 nếu mảng rỗng
            tb_ec_val = round(sum(ds_ec)/len(ds_ec), 2) if ds_ec else 0.0
            tb_ph_val = round(sum(ds_ph)/len(ds_ph), 2) if ds_ph else 0.0
            
            ket_qua_ngay_tho.append({
                'ngay': ngay,
                'nhan_ngay': f"Ngày {thu_tu} ({ngay.strftime('%d/%m/%Y')})",
                'so_lan': so_lan,
                'phut': round((giay_tong or 0)/60, 1),
                'tbec': tb_ec_val,
                'tbph': tb_ph_val,
                'ec_yc': dict_ec_yc.get(ngay, 0.0)
            })
        du_lieu_tong_hop.append(ket_qua_ngay_tho)
        
    return du_lieu_tong_hop

# ==========================================
# THUẬT TOÁN ĐỘNG (ĐÃ NÂNG CẤP XỬ LÝ AND ĐA BIẾN)
# ==========================================
def tinh_toan_giai_doan_dong(danh_sach_ngay, danh_sach_khoa, dict_sai_so):
    if not danh_sach_ngay or not danh_sach_khoa: return danh_sach_ngay
    
    gd_hien_tai = 1
    dict_chuan = {}
    for khoa in danh_sach_khoa:
        gia_tri = -1.0
        for d in danh_sach_ngay:
            if float(d[khoa]) > 0:
                gia_tri = float(d[khoa])
                break
        dict_chuan[khoa] = gia_tri if gia_tri != -1.0 else 0.0

    for i in range(len(danh_sach_ngay)):
        ngay_hien_tai = danh_sach_ngay[i]
        so_luong_lech = 0
        
        for khoa in danh_sach_khoa:
            gia_tri_nay = float(ngay_hien_tai[khoa])
            sai_so = dict_sai_so[khoa]
            
            if gia_tri_nay > 0:
                if abs(gia_tri_nay - dict_chuan[khoa]) > sai_so:
                    if i + 1 < len(danh_sach_ngay):
                        gia_tri_ngay_mai = float(danh_sach_ngay[i+1][khoa])
                        if gia_tri_ngay_mai > 0 and abs(gia_tri_ngay_mai - gia_tri_nay) <= sai_so:
                            so_luong_lech += 1
                            
        if so_luong_lech == len(danh_sach_khoa):
            gd_hien_tai += 1
            for khoa in danh_sach_khoa:
                dict_chuan[khoa] = float(ngay_hien_tai[khoa])
                
        ngay_hien_tai['giai_doan'] = gd_hien_tai
        
    return danh_sach_ngay

# ==========================================
# GIAO DIỆN HIỂN THỊ CẬP NHẬT
# ==========================================
def xuat_bao_cao_streamlit(du_lieu_vu, stt_vu, danh_sach_ten_chi_so_chon):
    so_ngay = len(du_lieu_vu)
    ngay_dau, ngay_cuoi = du_lieu_vu[0]['ngay'], du_lieu_vu[-1]['ngay']
    
    khoa_chi_so_input = MAP_CHI_SO[danh_sach_ten_chi_so_chon[0]] if danh_sach_ten_chi_so_chon else 'phut'
    ten_chi_so_hien_thi_chinh = danh_sach_ten_chi_so_chon[0] if danh_sach_ten_chi_so_chon else 'Tổng thời gian tưới (Phút)'

    st.markdown(f"### VỤ {stt_vu}: {ngay_dau.strftime('%d/%m/%Y')} ➔ {ngay_cuoi.strftime('%d/%m/%Y')} ({so_ngay} ngày)")
    
    nhan = [d['nhan_ngay'] for d in du_lieu_vu]
    ds_phut = [d['phut'] for d in du_lieu_vu]
    ds_tbec = [d['tbec'] if d['tbec'] > 0 else None for d in du_lieu_vu]
    ds_ec_yc = [d['ec_yc'] if d['ec_yc'] > 0 else None for d in du_lieu_vu]
    ds_giai_doan = [d['giai_doan'] for d in du_lieu_vu]

    # ---------------------------------------------------------
    # KHUNG THÔNG SỐ TỔNG QUAN (Metric Dashboard)
    # ---------------------------------------------------------
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
    # ---------------------------------------------------------

    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.08,
        row_heights=[0.60, 0.40], 
        subplot_titles=("<b>Biến động Thời Gian Tưới & EC</b>", f"<b>Phân tách GĐ (Biểu đồ hiển thị: {ten_chi_so_hien_thi_chinh})</b>"),
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

    fig.update_layout(
        height=900, 
        template="plotly_white", 
        hovermode="x unified", 
        margin=dict(l=30, r=30, t=60, b=20), 
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="right", x=1, bgcolor='rgba(255,255,255,0.7)'), 
        barmode='group',
        font=dict(family="Arial, sans-serif", size=13, color="#2c3e50") 
    )
    
    # Xóa toàn bộ đường kẻ lưới (showgrid=False)
    fig.update_xaxes(tickfont=dict(color="black", size=12), showgrid=False)
    fig.update_yaxes(title_text="<b>Tổng phút</b>", secondary_y=False, row=1, col=1, showgrid=False, tickfont=dict(color="black"))
    fig.update_yaxes(title_text="<b>Chỉ số EC</b>", secondary_y=True, row=1, col=1, showgrid=False, tickfont=dict(color="black"))
    fig.update_yaxes(title_text="<b>Giá trị</b>", row=2, col=1, showgrid=False, tickfont=dict(color="black"))

    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

    st.markdown("#### TỔNG KẾT CHI TIẾT THEO GIAI ĐOẠN")
    
    chon_gd = st.radio(
        f"Chọn Giai đoạn của Vụ {stt_vu} để xem chi tiết:", 
        options=giai_doan_duy_nhat, 
        format_func=lambda x: f"Giai đoạn {x}",
        key=f"chon_gd_vu_{stt_vu}",
        horizontal=True
    )

    data_gd = [d for d in du_lieu_vu if d['giai_doan'] == chon_gd]
    
    if data_gd:
        df_gd = pd.DataFrame(data_gd)
        df_gd = df_gd[['ngay', 'nhan_ngay', 'so_lan', 'phut', 'tbec', 'tbph', 'ec_yc', 'giai_doan']]
        df_gd.rename(columns={
            'ngay': 'Ngày',
            'nhan_ngay': 'Nhãn Ngày',
            'so_lan': 'Số Lần Tưới',
            'phut': 'Số Phút',
            'tbec': 'TBEC Thực',
            'tbph': 'TBpH',
            'ec_yc': 'EC Yêu Cầu',
            'giai_doan': 'Giai Đoạn'
        }, inplace=True)

        so_ngay_gd = len(df_gd)
        tb_lan = df_gd['Số Lần Tưới'].mean()
        tb_phut = df_gd['Số Phút'].mean()
        tb_tbec = df_gd['TBEC Thực'].mean()
        tb_tbph = df_gd['TBpH'].mean()
        tb_ec_yc = df_gd['EC Yêu Cầu'].mean()

        df_summary = pd.DataFrame([{
            'Ngày': 'TRUNG BÌNH/TỔNG',
            'Nhãn Ngày': f'{so_ngay_gd} ngày',
            'Số Lần Tưới': round(tb_lan, 1),
            'Số Phút': round(tb_phut, 1),
            'TBEC Thực': round(tb_tbec, 2),
            'TBpH': round(tb_tbph, 2),
            'EC Yêu Cầu': round(tb_ec_yc, 2),
            'Giai Đoạn': chon_gd
        }])

        df_hien_thi = pd.concat([df_gd, df_summary], ignore_index=True)

        map_cot_hien_thi = {
            'Tổng thời gian tưới (Phút)': 'Số Phút',
            'TBEC Thực tế': 'TBEC Thực',
            'EC Yêu cầu': 'EC Yêu Cầu'
        }
        
        danh_sach_cot_to_dam = [map_cot_hien_thi[ten] for ten in danh_sach_ten_chi_so_chon if ten in map_cot_hien_thi]

        # =========================================================
        # SỬA ĐÚNG KHÚC NÀY: TỐI ƯU HIGHLIGHT VECTOR KHÔNG DÙNG VÒNG LẶP FOR THEO DÒNG
        # =========================================================
        def highlight_table(df):
            df_style = pd.DataFrame('', index=df.index, columns=df.columns)
            css_dong_cuoi = 'font-weight: bold; background-color: #ecf0f1; color: #2c3e50; font-size: 18px !important;'
            df_style.iloc[-1, :] = css_dong_cuoi
            
            css_cot_highlight = 'font-weight: bold; color: #d35400; background-color: #fef9e7;'
            css_giao_cat = 'font-weight: bold; background-color: #ecf0f1; color: #d35400; font-size: 18px !important;'
            
            for cot in danh_sach_cot_to_dam:
                if cot in df_style.columns:
                    col_idx = df_style.columns.get_loc(cot)
                    # Nhuộm màu nguyên cột bằng phương pháp ma trận (Tốc độ ánh sáng, không treo)
                    df_style.iloc[:-1, col_idx] = css_cot_highlight
                    df_style.iloc[-1, col_idx] = css_giao_cat
                    
            return df_style
        # =========================================================

        format_mapping = {
            'Số Lần Tưới': lambda x: f"{x:g}" if isinstance(x, (int, float)) else x,
            'Số Phút': lambda x: f"{x:g}" if isinstance(x, (int, float)) else x,
            'TBEC Thực': lambda x: f"{x:g}" if isinstance(x, (int, float)) else x,
            'TBpH': lambda x: f"{x:g}" if isinstance(x, (int, float)) else x,
            'EC Yêu Cầu': lambda x: f"{x:g}" if isinstance(x, (int, float)) else x
        }

        chi_so_chuoi = " + ".join(danh_sach_cot_to_dam)
        st.caption(f"Chi tiết lịch sử tưới trong **Giai đoạn {chon_gd}** (Cột **{chi_so_chuoi}** đang được bôi sáng do là điều kiện AND):")
        st.dataframe(df_hien_thi.style.format(format_mapping).apply(highlight_table, axis=None), use_container_width=True, hide_index=True)


# ==========================================
# KHỞI TẠO APP
# ==========================================
st.set_page_config(page_title="Hệ Thống Phân Tích", page_icon="", layout="wide")

if 'da_bat_dau' not in st.session_state:
    st.session_state['da_bat_dau'] = False

with st.sidebar:
    st.header("TẢI FILE & CẤU HÌNH")
    
    file_ng = st.file_uploader("1. File: Lich nho giotj.json", type=['json'])
    file_cp = st.file_uploader("2. File: châm phân trung gian.json", type=['json'])
    
    st.divider()
    
    stt_khu = st.text_input("STT Khu (VD: 1, 2...):", value="1")
    
    st.markdown("**Phân chia Giai đoạn kết hợp (AND) theo:**")
    
    # NÂNG CẤP: Dùng Checkbox thay vì Multiselect
    ten_chi_so_chon = []
    for ten_chi_so in MAP_CHI_SO.keys():
        mac_dinh = True if ten_chi_so in ['EC Yêu cầu', 'TBEC Thực tế'] else False
        if st.checkbox(ten_chi_so, value=mac_dinh):
            ten_chi_so_chon.append(ten_chi_so)
    
    dict_sai_so_cai_dat = {}
    
    if ten_chi_so_chon:
        st.markdown("**Cài đặt sai số riêng cho từng chỉ số:**")
        for ten in ten_chi_so_chon:
            khoa = MAP_CHI_SO[ten]
            default_val = 15.0 if khoa == 'phut' else 0.20
            step_val = 1.0 if khoa == 'phut' else 0.05
            
            dict_sai_so_cai_dat[khoa] = st.number_input(f"- Sai số {ten}:", value=default_val, step=step_val)
    else:
        st.warning("Vui lòng chọn ít nhất 1 chỉ số để phân chia Giai đoạn!")
    
    st.divider()
    if st.button("CHẠY BÁO CÁO TỔNG HỢP", type="primary", use_container_width=True):
        st.session_state['da_bat_dau'] = True

st.title("HỆ THỐNG PHÂN TÍCH GIAI ĐOẠN ĐỘNG")

# CHÈN CSS ĐỂ TÙY CHỈNH GIAO DIỆN NÚT TÍCH (RADIO)
st.markdown(
    """
    <style>
    div[role="radiogroup"] label p {
        font-size: 18px !important; 
        font-weight: 500 !important;
    }
    div[role="radiogroup"] {
        gap: 15px 30px !important; 
        justify-content: flex-start;
    }
    /* Chỉnh CSS Metric Dashboard */
    div[data-testid="metric-container"] {
        background-color: transparent;
        padding: 5px;
    }
    </style>
    """, 
    unsafe_allow_html=True
)

if st.session_state['da_bat_dau']:
    if not ten_chi_so_chon:
        st.error("Lỗi: Phải chọn ít nhất 1 chỉ số ở cột bên trái để phân chia giai đoạn.")
    elif file_ng and file_cp:
        du_lieu_cac_vu_tho = chuan_bi_du_lieu_tho(file_ng.getvalue(), file_cp.getvalue(), stt_khu)
        
        if not du_lieu_cac_vu_tho:
            st.error(f"Không tìm thấy dữ liệu hợp lệ cho Khu {stt_khu}.")
        else:
            danh_sach_khoa = [MAP_CHI_SO[ten] for ten in ten_chi_so_chon]
            
            danh_sach_tuy_chon = []
            map_thu_tu_vu = {} 
            
            for i, vu in enumerate(du_lieu_cac_vu_tho):
                ngay_dau_str = vu[0]['ngay'].strftime('%d/%m/%Y')
                ngay_cuoi_str = vu[-1]['ngay'].strftime('%d/%m/%Y')
                so_ngay = len(vu)
                
                ten_hien_thi = f"Vụ {i+1}: {ngay_dau_str} ➔ {ngay_cuoi_str} ({so_ngay} ngày)"
                danh_sach_tuy_chon.append(ten_hien_thi)
                map_thu_tu_vu[ten_hien_thi] = i + 1 
                
            nhan_tuy_chinh = "Tra cứu khoảng ngày tùy chỉnh"
            danh_sach_tuy_chon.append(nhan_tuy_chinh)
            
            che_do_xem = st.radio(
                label="Chọn nội dung xem", 
                options=danh_sach_tuy_chon, 
                horizontal=True,
                label_visibility="collapsed" 
            )
            
            if che_do_xem != nhan_tuy_chinh:
                stt_vu_chon = map_thu_tu_vu[che_do_xem]
                
                data_vu = copy.deepcopy(du_lieu_cac_vu_tho[stt_vu_chon - 1])
                ket_qua_gd = tinh_toan_giai_doan_dong(data_vu, danh_sach_khoa, dict_sai_so_cai_dat)
                xuat_bao_cao_streamlit(ket_qua_gd, stt_vu_chon, ten_chi_so_chon)
                
            else:
                st.markdown("### LỌC DỮ LIỆU THEO NGÀY TÙY CHỌN")
                tat_ca_ngay = [d for vu in du_lieu_cac_vu_tho for d in vu]
                ngay_min, ngay_max = tat_ca_ngay[0]['ngay'], tat_ca_ngay[-1]['ngay']
                
                if 'ngay_bat_dau_custom' not in st.session_state:
                    st.session_state['ngay_bat_dau_custom'] = ngay_min
                if 'ngay_ket_thuc_custom' not in st.session_state:
                    st.session_state['ngay_ket_thuc_custom'] = ngay_max
                
                col1, col2 = st.columns(2)
                ngay_bat_dau = col1.date_input("Từ ngày:", value=st.session_state['ngay_bat_dau_custom'], min_value=ngay_min, max_value=ngay_max)
                ngay_ket_thuc = col2.date_input("Đến ngày:", value=st.session_state['ngay_ket_thuc_custom'], min_value=ngay_min, max_value=ngay_max)
                
                st.session_state['ngay_bat_dau_custom'] = ngay_bat_dau
                st.session_state['ngay_ket_thuc_custom'] = ngay_ket_thuc
                
                if ngay_bat_dau > ngay_ket_thuc:
                    st.error("Lỗi: 'Từ ngày' không được lớn hơn 'Đến ngày'.")
                else:
                    du_lieu_tuy_chinh_cac_vu = []
                    for vu in du_lieu_cac_vu_tho:
                        vu_da_loc = [d for d in vu if ngay_bat_dau <= d['ngay'] <= ngay_ket_thuc]
                        if len(vu_da_loc) >= SO_NGAY_TOI_THIEU_VU:
                            du_lieu_tuy_chinh_cac_vu.append(vu_da_loc)
                    
                    if not du_lieu_tuy_chinh_cac_vu:
                        st.warning(f"Trong khoảng thời gian bạn chọn, không có chuỗi ngày liên tục nào đạt đủ {SO_NGAY_TOI_THIEU_VU} ngày để tạo thành 1 Vụ hợp lệ.")
                    else:
                        for i, vu_custom in enumerate(du_lieu_tuy_chinh_cac_vu, 1):
                            data_custom = copy.deepcopy(vu_custom)
                            ket_qua_gd_custom = tinh_toan_giai_doan_dong(data_custom, danh_sach_khoa, dict_sai_so_cai_dat)
                            
                            ten_vu_hien_thi = f"Tùy Chỉnh {i}" if len(du_lieu_tuy_chinh_cac_vu) > 1 else "Tùy Chỉnh"
                            xuat_bao_cao_streamlit(ket_qua_gd_custom, ten_vu_hien_thi, ten_chi_so_chon)
                            st.markdown("<br>", unsafe_allow_html=True)

    else:
        st.info("Hãy tải đủ 2 file JSON ở cột bên trái và bấm Chạy Báo Cáo.")