import math
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Vận tốc ánh sáng trong chân không (m/s)
C_SPEED = 299792458.0
# Trở kháng không gian tự do Z0_air = sqrt(mu0/eps0) ~ 120 * pi
Z0_AIR = 120.0 * math.pi

@app.route('/')
def home():
    return render_template('index.html')

# 1. CÁP ĐỒNG TRỤC (Coaxial Cable)
@app.route('/calculate_coaxial', methods=['POST'])
def calculate_coaxial():
    try:
        data = request.get_json()
        er = float(data.get('er', 0))
        d = float(data.get('d', 0))
        D = float(data.get('D', 0))

        if er <= 0 or d <= 0 or D <= 0:
            return jsonify({'error': 'Các tham số phải lớn hơn 0!'}), 400
        if D <= d:
            return jsonify({'error': 'Đường kính vỏ ngoài D phải lớn hơn đường kính lõi d!'}), 400

        log_ratio = math.log10(D / d)
        sqrt_er = math.sqrt(er)

        # Công thức Slide trang 38
        z0 = (138.0 * log_ratio) / sqrt_er
        c_val = (24.13 * er) / log_ratio
        l_val = 460.6 * log_ratio
        fc = 190.85 / ((D + d) * sqrt_er)
        vp_m_s = C_SPEED / sqrt_er
        vp_km_s = vp_m_s / 1000.0
        td_ns_m = 1000.0 / (vp_m_s / 1e6)

        return jsonify({
            'z0': round(z0, 2),
            'C': round(c_val, 2),
            'L': round(l_val, 2),
            'fc': round(fc, 3),
            'vp': round(vp_km_s, 2),
            'td': round(td_ns_m, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 2. ỐNG DẪN SÓNG HÌNH CHỮ NHẬT (Rectangular Waveguide)
@app.route('/calculate_rect_wg', methods=['POST'])
def calculate_rect_wg():
    try:
        data = request.get_json()
        a_mm = float(data.get('a', 0))
        b_mm = float(data.get('b', 0))
        mode_type = str(data.get('mode_type', 'TE')).upper()
        m = int(data.get('m', 1))
        n = int(data.get('n', 0))
        f_ghz = float(data.get('f', 0))
        er = float(data.get('er', 1.0))

        if a_mm <= 0 or b_mm <= 0 or f_ghz <= 0 or er <= 0:
            return jsonify({'error': 'Kích thước, tần số và er phải lớn hơn 0!'}), 400
        if mode_type == 'TM' and (m == 0 or n == 0):
            return jsonify({'error': 'Mốt sóng TM yêu cầu m >= 1 và n >= 1!'}), 400
        if mode_type == 'TE' and m == 0 and n == 0:
            return jsonify({'error': 'Mốt sóng TE00 không tồn tại!'}), 400

        a = a_mm / 1000.0
        b = b_mm / 1000.0
        v = C_SPEED / math.sqrt(er)

        # Công thức Slide trang 22, 23
        kc = math.sqrt((m * math.pi / a)**2 + (n * math.pi / b)**2)
        fc_hz = (v / (2.0 * math.pi)) * kc
        fc_ghz = fc_hz / 1e9
        lc_mm = (v / fc_hz) * 1000.0

        f_hz = f_ghz * 1e9
        z_wave = 0.0

        if f_hz > fc_hz:
            factor = math.sqrt(1.0 - (fc_hz / f_hz)**2)
            z0_dielectric = Z0_AIR / math.sqrt(er)
            if mode_type == 'TE':
                z_wave = z0_dielectric / factor  # Slide trang 22
            else:
                z_wave = z0_dielectric * factor  # Slide trang 23

        return jsonify({
            'fc': round(fc_ghz, 3),
            'lc': round(lc_mm, 2),
            'zwave': round(z_wave, 2) if z_wave > 0 else "Cắt sóng (f < fc)"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 3. ỐNG DẪN SÓNG HÌNH TRỤ TRÒN (Circular Waveguide)
@app.route('/calculate_circ_wg', methods=['POST'])
def calculate_circ_wg():
    try:
        data = request.get_json()
        a_mm = float(data.get('a', 0))
        er = float(data.get('er', 1.0))
        mode_type = str(data.get('mode_type', 'TE')).upper()
        m = int(data.get('m', 1))
        n = int(data.get('n', 1))

        if a_mm <= 0 or er <= 0:
            return jsonify({'error': 'Bán kính và er phải lớn hơn 0!'}), 400

        # Bảng tra nghiệm hàm Bessel (chi_mn và nu_mn) từ Slide trang 33
        bessel_roots = {
            'TM': {(0, 1): 2.405, (0, 2): 5.520, (1, 1): 3.830},
            'TE': {(0, 1): 3.830, (1, 1): 1.840}
        }

        root = bessel_roots.get(mode_type, {}).get((m, n))

        # Nếu không thuộc mốt đặc biệt trong Slide, dùng nghiệm xấp xỉ tổng quát
        if root is None:
            if mode_type == 'TM':
                root = (n + m / 2.0 - 0.25) * math.pi
            else:
                root = (n + m / 2.0 + 0.25) * math.pi

        a = a_mm / 1000.0
        v = C_SPEED / math.sqrt(er)

        # Công thức Slide trang 30, 32
        fc_hz = (root * v) / (2.0 * math.pi * a)
        fc_ghz = fc_hz / 1e9
        lc_mm = (v / fc_hz) * 1000.0

        return jsonify({
            'fc': round(fc_ghz, 3),
            'lc': round(lc_mm, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 4. ĐƯỜNG TRUYỀN MẠCH IN (Microstrip Line)
@app.route('/calculate_microstrip', methods=['POST'])
def calculate_microstrip():
    try:
        data = request.get_json()
        w = float(data.get('w', 0))
        d = float(data.get('d', 0))
        er = float(data.get('er', 0))

        if w <= 0 or d <= 0 or er <= 0:
            return jsonify({'error': 'Các tham số phải lớn hơn 0!'}), 400

        wd_ratio = w / d

        # Công thức Slide trang 44: Hằng số điện môi hiệu dụng eps_e
        eeff = ((er + 1.0) / 2.0) + ((er - 1.0) / 2.0) * (1.0 / math.sqrt(1.0 + 12.0 * (d / w)))

        # Công thức Slide trang 45: Trở kháng đặc tính Z0
        if wd_ratio <= 1.0:
            z0 = (60.0 / math.sqrt(eeff)) * math.log((8.0 * d / w) + (w / (4.0 * d)))
        else:
            term = wd_ratio + 1.393 + 0.667 * math.log(wd_ratio + 1.444)
            z0 = (120.0 * math.pi) / (math.sqrt(eeff) * term)

        return jsonify({
            'wd_ratio': round(wd_ratio, 3),
            'eeff': round(eeff, 3),
            'z0': round(z0, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# 5. ĐƯỜNG TRUYỀN HAI DÂY (Two-Wire Line / Parallel-Wire Line)
@app.route('/calculate_twowire', methods=['POST'])
def calculate_twowire():
    try:
        data = request.get_json()
        er = float(data.get('er', 1.0))
        d = float(data.get('d', 0))  # Đường kính mỗi dây (mm)
        D = float(data.get('D', 0))  # Khoảng cách giữa tâm 2 dây (mm)

        if er <= 0 or d <= 0 or D <= 0:
            return jsonify({'error': 'Các tham số phải lớn hơn 0!'}), 400
        if D <= d:
            return jsonify({'error': 'Khoảng cách D giữa hai tâm dây phải lớn hơn đường kính dây d!'}), 400

        sqrt_er = math.sqrt(er)
        
        # Trở kháng đặc tính Z0 (Ohm)
        # Công thức gần đúng chuẩn cho D >> d: Z0 = (120 / sqrt(er)) * ln(2D / d)
        # Hoặc dùng arcosh: Z0 = (120 / sqrt(er)) * acosh(D / d)
        z0 = (120.0 / sqrt_er) * math.acosh(D / d)

        # Điện dung trên một đơn vị chiều dài C' (pF/m)
        c_val = (math.pi * 8.854e-12 * er / math.acosh(D / d)) * 1e12

        # Độ tự cảm trên một đơn vị chiều dài L' (nH/m)
        l_val = ((4e-7 * math.pi / math.pi) * math.acosh(D / d)) * 1e9

        # Vận tốc lan truyền Vp (km/s) và Thời gian trễ td (ns/m)
        vp_m_s = C_SPEED / sqrt_er
        vp_km_s = vp_m_s / 1000.0
        td_ns_m = 1000.0 / (vp_m_s / 1e6)

        return jsonify({
            'z0': round(z0, 2),
            'C': round(c_val, 2),
            'L': round(l_val, 2),
            'vp': round(vp_km_s, 2),
            'td': round(td_ns_m, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)