import sys
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QGroupBox, QDoubleSpinBox, QFormLayout, 
                             QMessageBox, QCheckBox, QFileDialog, QGridLayout, 
                             QGraphicsView, QGraphicsScene, QSlider)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap, QPainter
import cv2
import numpy as np

# Dicionário mapeando Seriais para nomes de interface
CAMERA_NAMES = {
    '19337756': 'FPP_LEFT',
    '19337638': 'FPP_RIGHT',
    '22348163': 'DEFL_LEFT',
    '22348161': 'DEFL_RIGHT'
}

class ZoomableView(QGraphicsView):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = self.scene.addPixmap(QPixmap())
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        
        self.setStyleSheet("background-color: black;")
        self._is_empty = True
        self.title = title

    def set_image(self, q_img):
        pixmap = QPixmap.fromImage(q_img)
        self.pixmap_item.setPixmap(pixmap)
        
        # Apenas ajusta para caber na view na primeira vez
        if self._is_empty:
            self.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            self._is_empty = False

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        self.scale(zoom_factor, zoom_factor)
        
    def clear(self):
        self.pixmap_item.setPixmap(QPixmap())
        self._is_empty = True


class CalibratorGUI(QWidget):
    def __init__(self, camera_manager, CalibrationManagerClass):
        super().__init__()
        self.cam_manager = camera_manager
        
        # Guardar a classe para instanciar depois
        self.CalibrationManagerClass = CalibrationManagerClass
        
        # Dicionário de instâncias de calibração por serial
        self.cal_managers = {
            serial: self.CalibrationManagerClass() for serial in CAMERA_NAMES.keys()
        }
        
        # Dicionário para armazenar o último resultado de cantos processados
        self.last_charuco_data = {serial: (None, None) for serial in CAMERA_NAMES.keys()}
        self.calibration_results = {}
        
        self.setWindowTitle("FLIR Camera Calibrator - 4 Câmeras (ChArUco)")
        self.resize(1400, 900)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        
        self.init_ui()

    def create_camera_controls(self, group_name):
        group = QGroupBox(f"Controles: {group_name}")
        form = QFormLayout()

        spin_exposure = QDoubleSpinBox()
        spin_exposure.setRange(10.0, 100000.0)
        spin_exposure.setValue(5000.0)
        spin_exposure.setSingleStep(500.0)
        spin_exposure.valueChanged.connect(lambda v, g=group_name: self.cam_manager.set_exposure(g, v))
        form.addRow("Exposure Time (us):", spin_exposure)

        spin_gain = QDoubleSpinBox()
        spin_gain.setRange(0.0, 40.0)
        spin_gain.setValue(0.0)
        spin_gain.setSingleStep(1.0)
        spin_gain.valueChanged.connect(lambda v, g=group_name: self.cam_manager.set_gain(g, v))
        form.addRow("Gain (dB):", spin_gain)

        spin_gamma = QDoubleSpinBox()
        spin_gamma.setRange(0.1, 4.0)
        spin_gamma.setValue(1.0)
        spin_gamma.setSingleStep(0.1)
        spin_gamma.valueChanged.connect(lambda v, g=group_name: self.cam_manager.set_gamma(g, v))
        form.addRow("Gamma:", spin_gamma)

        spin_black = QDoubleSpinBox()
        spin_black.setRange(0.0, 10.0)
        spin_black.setValue(0.0)
        spin_black.setSingleStep(0.1)
        spin_black.valueChanged.connect(lambda v, g=group_name: self.cam_manager.set_black_level(g, v))
        form.addRow("Black Level (%):", spin_black)

        chk_wb_auto = QCheckBox("Auto White Balance")
        chk_wb_auto.stateChanged.connect(lambda state, g=group_name: self.cam_manager.set_white_balance_auto(g, state == Qt.Checked))
        form.addRow("White Balance:", chk_wb_auto)

        slider_line_y = QSlider(Qt.Horizontal)
        slider_line_y.setRange(0, 100)
        slider_line_y.setValue(50)
        slider_line_y.valueChanged.connect(lambda v, g=group_name: self.update_line_y(g, v))
        form.addRow("Altura Linha Y (%):", slider_line_y)

        group.setLayout(form)
        return group, spin_exposure, spin_gain, spin_gamma, spin_black, slider_line_y

    def update_line_y(self, group_name, value):
        ratio = value / 100.0
        serials = self.cam_manager.groups.get(group_name, [])
        for serial in serials:
            mgr = self.cal_managers.get(serial)
            if mgr:
                mgr.line_y_ratio = ratio

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        # Esquerda: Feed de Vídeo e Gráficos
        video_layout = QGridLayout()
        
        self.views = {}
        
        def add_view(serial, title, row, col):
            container = QVBoxLayout()
            lbl = QLabel(title)
            lbl.setAlignment(Qt.AlignCenter)
            view = ZoomableView(title)
            view.setMinimumSize(400, 300)
            container.addWidget(lbl)
            container.addWidget(view)
            video_layout.addLayout(container, row, col)
            self.views[serial] = view

        # Linha 0: FPP Cameras
        add_view('19337756', 'FPP_LEFT (19337756)', 0, 0)
        add_view('19337638', 'FPP_RIGHT (19337638)', 0, 1)
        
        # Linha 1: Gráfico FPP
        self.lbl_graph_fpp = QLabel("FPP Graph")
        self.lbl_graph_fpp.setMinimumHeight(180)
        self.lbl_graph_fpp.setMaximumHeight(220)
        self.lbl_graph_fpp.setStyleSheet("background-color: black; border: 1px solid gray;")
        self.lbl_graph_fpp.setScaledContents(True)
        video_layout.addWidget(self.lbl_graph_fpp, 1, 0, 1, 2)
        
        # Linha 2: DEFL Cameras
        add_view('22348163', 'DEFL_LEFT (22348163)', 2, 0)
        add_view('22348161', 'DEFL_RIGHT (22348161)', 2, 1)
        
        # Linha 3: Gráfico DEFL
        self.lbl_graph_defl = QLabel("DEFL Graph")
        self.lbl_graph_defl.setMinimumHeight(180)
        self.lbl_graph_defl.setMaximumHeight(220)
        self.lbl_graph_defl.setStyleSheet("background-color: black; border: 1px solid gray;")
        self.lbl_graph_defl.setScaledContents(True)
        video_layout.addWidget(self.lbl_graph_defl, 3, 0, 1, 2)
        
        main_layout.addLayout(video_layout, stretch=4)

        # Direita: Controles
        control_layout = QVBoxLayout()

        self.btn_connect = QPushButton("Conectar Câmeras")
        self.btn_connect.clicked.connect(self.toggle_connection)
        control_layout.addWidget(self.btn_connect)

        # Controles FPP
        fpp_group, self.fpp_exp, self.fpp_gain, self.fpp_gamma, self.fpp_black, _ = self.create_camera_controls('FPP')
        control_layout.addWidget(fpp_group)

        # Controles DEFL
        defl_group, self.defl_exp, self.defl_gain, self.defl_gamma, self.defl_black, _ = self.create_camera_controls('DEFL')
        control_layout.addWidget(defl_group)

        # Configurações do Padrão ChArUco
        charuco_group = QGroupBox("Padrão ChArUco")
        charuco_form = QFormLayout()

        first_manager = list(self.cal_managers.values())[0]

        self.spin_sq_len = QDoubleSpinBox()
        self.spin_sq_len.setDecimals(3)
        self.spin_sq_len.setRange(0.001, 1.000)
        self.spin_sq_len.setValue(first_manager.square_length)
        self.spin_sq_len.setSingleStep(0.001)

        self.spin_mk_len = QDoubleSpinBox()
        self.spin_mk_len.setDecimals(3)
        self.spin_mk_len.setRange(0.001, 1.000)
        self.spin_mk_len.setValue(first_manager.marker_length)
        self.spin_mk_len.setSingleStep(0.001)

        self.btn_update_board = QPushButton("Atualizar Padrão")
        self.btn_update_board.clicked.connect(self.update_board)

        charuco_form.addRow("Square Length (m):", self.spin_sq_len)
        charuco_form.addRow("Marker Length (m):", self.spin_mk_len)
        charuco_form.addRow(self.btn_update_board)
        charuco_group.setLayout(charuco_form)
        control_layout.addWidget(charuco_group)

        # Controles de Calibração
        calib_group = QGroupBox("Calibração Independente")
        calib_vbox = QVBoxLayout()

        self.lbl_poses = QLabel("Poses capturadas: 0")
        calib_vbox.addWidget(self.lbl_poses)

        self.btn_capture = QPushButton("Capturar Posição Atual")
        self.btn_capture.clicked.connect(self.capture_pose)
        calib_vbox.addWidget(self.btn_capture)

        self.btn_clear = QPushButton("Limpar Capturas")
        self.btn_clear.clicked.connect(self.clear_poses)
        calib_vbox.addWidget(self.btn_clear)

        self.btn_calibrate = QPushButton("Executar Calibração")
        self.btn_calibrate.clicked.connect(self.run_calibration)
        calib_vbox.addWidget(self.btn_calibrate)

        self.btn_save = QPushButton("Salvar Parâmetros")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self.save_params)
        calib_vbox.addWidget(self.btn_save)

        calib_group.setLayout(calib_vbox)
        control_layout.addWidget(calib_group)
        
        control_layout.addStretch()
        main_layout.addLayout(control_layout, stretch=1)

    def toggle_connection(self):
        if not self.cam_manager.is_streaming:
            success, msg = self.cam_manager.connect()
            if success:
                self.cam_manager.set_exposure('FPP', self.fpp_exp.value())
                self.cam_manager.set_gain('FPP', self.fpp_gain.value())
                self.cam_manager.set_gamma('FPP', self.fpp_gamma.value())
                self.cam_manager.set_black_level('FPP', self.fpp_black.value())
                
                self.cam_manager.set_exposure('DEFL', self.defl_exp.value())
                self.cam_manager.set_gain('DEFL', self.defl_gain.value())
                self.cam_manager.set_gamma('DEFL', self.defl_gamma.value())
                self.cam_manager.set_black_level('DEFL', self.defl_black.value())
                
                self.cam_manager.start_stream()
                self.timer.start(30) # ~33 FPS
                self.btn_connect.setText("Desconectar Câmeras")
            else:
                QMessageBox.critical(self, "Erro", msg)
        else:
            self.timer.stop()
            self.cam_manager.disconnect()
            self.btn_connect.setText("Conectar Câmeras")
            for view in self.views.values():
                view.clear()
            self.lbl_graph_fpp.clear()
            self.lbl_graph_defl.clear()

    def update_board(self):
        sq = self.spin_sq_len.value()
        mk = self.spin_mk_len.value()
        for mgr in self.cal_managers.values():
            mgr.update_board_params(sq, mk)
        QMessageBox.information(self, "Padrão Atualizado", "Dimensões do ChArUco atualizadas em todas as câmeras.")

    def create_graph_image(self, profile_left, profile_right):
        img_width = 1200
        img_height = 240
        margin_left = 70
        margin_bottom = 50
        margin_top = 30
        margin_right = 30
        
        plot_width = img_width - margin_left - margin_right
        plot_height = img_height - margin_bottom - margin_top
        
        graph_img = np.zeros((img_height, img_width, 3), dtype=np.uint8)
        # Preencher o fundo da área do gráfico de verde escuro
        cv2.rectangle(graph_img, (margin_left, margin_top), (margin_left + plot_width, margin_top + plot_height), (0, 25, 0), -1)
        
        # Borda
        cv2.rectangle(graph_img, (margin_left, margin_top), (margin_left + plot_width, margin_top + plot_height), (100, 100, 100), 1)
        
        # Eixo Y (Intensidade)
        num_y_ticks = 6
        for i in range(num_y_ticks):
            val = int(255 * i / (num_y_ticks - 1))
            y = margin_top + plot_height - int(plot_height * val / 255.0)
            cv2.line(graph_img, (margin_left, y), (margin_left + plot_width, y), (0, 50, 0), 1)
            text_size = cv2.getTextSize(str(val), cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
            cv2.putText(graph_img, str(val), (margin_left - text_size[0] - 10, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            
        # Determinar max_pixels do eixo X
        max_pixels = 1600
        if profile_left is not None:
            max_pixels = len(profile_left)
        elif profile_right is not None:
            max_pixels = len(profile_right)
            
        # Eixo X (Nº pixel)
        num_x_ticks = 9
        for i in range(num_x_ticks):
            x = margin_left + int(plot_width * i / (num_x_ticks - 1))
            cv2.line(graph_img, (x, margin_top), (x, margin_top + plot_height), (0, 50, 0), 1)
            val_x = int(max_pixels * i / (num_x_ticks - 1))
            text_size = cv2.getTextSize(str(val_x), cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
            cv2.putText(graph_img, str(val_x), (x - text_size[0]//2, margin_top + plot_height + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            
        # Título e Labels
        cv2.putText(graph_img, "Intensidade vs Pixel", (10, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(graph_img, "Intensidade", (5, margin_top - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        cv2.putText(graph_img, "Numero do Pixel", (margin_left + plot_width // 2 - 40, margin_top + plot_height + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
        def draw_profile(profile, color):
            if profile is not None:
                x_old = np.linspace(0, plot_width - 1, len(profile))
                x_new = np.arange(plot_width)
                profile_resized = np.interp(x_new, x_old, profile)
                
                y_plot = margin_top + plot_height - 1 - (profile_resized * (plot_height - 1) / 255.0)
                x_plot = margin_left + x_new
                
                pts = np.column_stack((x_plot, y_plot)).astype(np.int32).reshape((-1, 1, 2))
                cv2.polylines(graph_img, [pts], isClosed=False, color=color, thickness=1)

        # OpenCV BGR -> Branco (Esq) e Vermelho (Dir)
        draw_profile(profile_left, (255, 255, 255))
        draw_profile(profile_right, (0, 0, 255))
        
        return graph_img

    def update_frame(self):
        if not self.cam_manager.is_streaming:
            self.timer.stop()
            self.cam_manager.disconnect()
            self.btn_connect.setText("Conectar Câmeras")
            for view in self.views.values():
                view.clear()
            self.lbl_graph_fpp.clear()
            self.lbl_graph_defl.clear()
            return

        frames = self.cam_manager.get_frames()
        if not frames:
            return
            
        profiles = {
            'FPP': {'LEFT': None, 'RIGHT': None},
            'DEFL': {'LEFT': None, 'RIGHT': None}
        }
            
        for serial, frame in frames.items():
            if frame is None or serial not in self.views:
                continue
                
            mgr = self.cal_managers.get(serial)
            if mgr:
                processed_frame, corners, ids, profile = mgr.process_frame(frame)
                self.last_charuco_data[serial] = (corners, ids)
                
                if serial == '19337756': profiles['FPP']['LEFT'] = profile
                elif serial == '19337638': profiles['FPP']['RIGHT'] = profile
                elif serial == '22348163': profiles['DEFL']['LEFT'] = profile
                elif serial == '22348161': profiles['DEFL']['RIGHT'] = profile
                
                rgb_image = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                self.views[serial].set_image(q_img)

        # Atualiza o gráfico FPP
        img_fpp = self.create_graph_image(profiles['FPP']['LEFT'], profiles['FPP']['RIGHT'])
        # QImage usa RGB, mas o numpy array está em BGR (gerado pelo cv2), então usamos cvtColor
        img_fpp_rgb = cv2.cvtColor(img_fpp, cv2.COLOR_BGR2RGB)
        q_img_fpp = QImage(img_fpp_rgb.data, img_fpp_rgb.shape[1], img_fpp_rgb.shape[0], img_fpp_rgb.shape[1]*3, QImage.Format_RGB888)
        self.lbl_graph_fpp.setPixmap(QPixmap.fromImage(q_img_fpp))
        
        # Atualiza o gráfico DEFL
        img_defl = self.create_graph_image(profiles['DEFL']['LEFT'], profiles['DEFL']['RIGHT'])
        img_defl_rgb = cv2.cvtColor(img_defl, cv2.COLOR_BGR2RGB)
        q_img_defl = QImage(img_defl_rgb.data, img_defl_rgb.shape[1], img_defl_rgb.shape[0], img_defl_rgb.shape[1]*3, QImage.Format_RGB888)
        self.lbl_graph_defl.setPixmap(QPixmap.fromImage(q_img_defl))

    def capture_pose(self):
        captured_any = False
        
        for serial, (corners, ids) in self.last_charuco_data.items():
            if corners is not None and len(corners) >= 4:
                mgr = self.cal_managers.get(serial)
                if mgr and mgr.add_capture(corners, ids):
                    captured_any = True
                    
        if captured_any:
            max_count = max([len(mgr.all_corners) for mgr in self.cal_managers.values()])
            self.lbl_poses.setText(f"Poses capturadas: {max_count}")
        else:
            QMessageBox.warning(self, "Aviso", "Nenhuma câmera detectou o tabuleiro suficientemente.")

    def clear_poses(self):
        for mgr in self.cal_managers.values():
            mgr.clear_captures()
        self.lbl_poses.setText("Poses capturadas: 0")
        self.calibration_results.clear()
        self.btn_save.setEnabled(False)

    def run_calibration(self):
        results_msg = ""
        any_success = False
        
        for serial, mgr in self.cal_managers.items():
            cam_name = CAMERA_NAMES.get(serial, serial)
            if len(mgr.all_corners) < 5:
                results_msg += f"{cam_name}: Poucas capturas ({len(mgr.all_corners)}).\n"
                continue
                
            success, result = mgr.calibrate()
            if success:
                self.calibration_results[serial] = result
                rms = result["rms"]
                results_msg += f"{cam_name}: SUCESSO (RMS: {rms:.4f})\n"
                any_success = True
            else:
                results_msg += f"{cam_name}: ERRO - {result}\n"

        if any_success:
            self.btn_save.setEnabled(True)
            QMessageBox.information(self, "Resultado da Calibração", results_msg)
        else:
            QMessageBox.warning(self, "Calibração Falhou", results_msg)

    def save_params(self):
        if not self.calibration_results:
            return
            
        dir_path = QFileDialog.getExistingDirectory(self, "Selecionar pasta raiz para salvar", ".")
        if dir_path:
            saved_paths = []
            for serial, result in self.calibration_results.items():
                cam_name = CAMERA_NAMES.get(serial, serial)
                cam_dir = os.path.join(dir_path, cam_name)
                
                os.makedirs(cam_dir, exist_ok=True)
                mgr = self.cal_managers[serial]
                try:
                    mgr.save_calibration(result, cam_dir)
                    saved_paths.append(cam_dir)
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Erro ao salvar {cam_name}: {e}")
                    
            if saved_paths:
                QMessageBox.information(self, "Sucesso", f"Parâmetros salvos nas pastas:\n" + "\n".join(saved_paths))

    def closeEvent(self, event):
        self.cam_manager.disconnect()
        event.accept()
