# ==========================================
# GIAO DIỆN HIỂN THỊ CẬP NHẬT (ĐÃ TỐI ƯU TỐC ĐỘ)
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

    fig.update_layout(
        height=900, 
        template="plotly_white", 
        hovermode="x unified", 
        margin=dict(l=30, r=30, t=60, b=20), 
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="right", x=1, bgcolor='rgba(255,255,255,0.7)'), 
        barmode='group',
        font=dict(family="Arial, sans-serif", size=13, color="#2c3e50") 
    )
    
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
        # =========================================================
        # BIỂU ĐỒ CHI TIẾT CHO GIAI ĐOẠN ĐƯỢC CHỌN
        # =========================================================
        x_gd_chart = [d['nhan_ngay'] for d in data_gd]
        y_phut_gd = [d['phut'] for d in data_gd]
        y_tbec_gd = [d['tbec'] if d['tbec'] > 0 else None for d in data_gd]
        y_ec_yc_gd = [d['ec_yc'] if d['ec_yc'] > 0 else None for d in data_gd]

        fig_gd = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig_gd.add_trace(go.Bar(x=x_gd_chart, y=y_phut_gd, name='Thời gian tưới (Phút)', marker_color='#aed6f1', opacity=0.8), secondary_y=False)
        fig_gd.add_trace(go.Scatter(x=x_gd_chart, y=y_tbec_gd, name='TBEC Thực', mode='lines+markers', line=dict(color='#e74c3c', width=2)), secondary_y=True)
        fig_gd.add_trace(go.Scatter(x=x_gd_chart, y=y_ec_yc_gd, name='EC Yêu Cầu', mode='lines+markers', line=dict(color='#9b59b6', width=2, dash='dot')), secondary_y=True)

        fig_gd.update_layout(
            title=f"<b>Biểu đồ thông số chi tiết - Giai đoạn {chon_gd}</b>",
            height=400, 
            template="plotly_white", 
            hovermode="x unified",
            margin=dict(l=20, r=20, t=50, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
        )
        fig_gd.update_xaxes(showgrid=False)
        fig_gd.update_yaxes(title_text="<b>Tổng phút</b>", secondary_y=False, showgrid=False)
        fig_gd.update_yaxes(title_text="<b>Chỉ số EC</b>", secondary_y=True, showgrid=False)
        
        st.plotly_chart(fig_gd, use_container_width=True, config={'displayModeBar': False})
        # =========================================================

        # ===== XỬ LÝ BẢNG SỐ LIỆU =====
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
        # HÀM HIGHLIGHT ĐÃ TỐI ƯU (BỎ VÒNG LẶP FOR THEO DÒNG)
        # =========================================================
        def highlight_table(df):
            # Tạo DataFrame rỗng cùng kích thước với df để chứa thuộc tính CSS
            df_style = pd.DataFrame('', index=df.index, columns=df.columns)
            
            # 1. Định dạng dòng tổng kết cuối cùng (Sử dụng cơ chế gán toàn bộ dòng nhanh)
            css_dong_cuoi = 'font-weight: bold; background-color: #ecf0f1; color: #2c3e50; font-size: 18px !important;'
            df_style.iloc[-1, :] = css_dong_cuoi
            
            # 2. Định dạng cột được chọn (Sử dụng cơ chế cắt lát Vectorized - KHÔNG DÙNG VÒNG LẶP FOR THEO DÒNG)
            css_cot_highlight = 'font-weight: bold; color: #d35400; background-color: #fef9e7;'
            css_giao_cat = 'font-weight: bold; background-color: #ecf0f1; color: #d35400; font-size: 18px !important;'
            
            for cot in danh_sach_cot_to_dam:
                if cot in df_style.columns:
                    col_idx = df_style.columns.get_loc(cot)
                    # Tô màu toàn bộ cột ngoại trừ ô cuối cùng
                    df_style.iloc[:-1, col_idx] = css_cot_highlight
                    # Riêng ô giao nhau ở dòng cuối cùng sẽ lấy màu của ô giao cắt
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

        chi_so_chuoi = " + ".join(danh_sach_cot_to_dam) if danh_sach_cot_to_dam else "Không"
        st.caption(f"Chi tiết lịch sử tưới trong **Giai đoạn {chon_gd}** (Cột **{chi_so_chuoi}** đang được bôi sáng do là điều kiện AND):")
        st.dataframe(df_hien_thi.style.format(format_mapping).apply(highlight_table, axis=None), use_container_width=True, hide_index=True)