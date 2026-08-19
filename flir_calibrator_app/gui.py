import sys
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QGroupBox, QDoubleSpinBox, QFormLayout, 
                             QMessageBox, QCheckBox, QFileDialog, QGridLayout, QGraphicsView, QGraphicsScene)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap, QPainter
import cv2

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
        self.resize(1200, 800)
        
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

        group.setLayout(form)
        
        return group, spin_exposure, spin_gain, spin_gamma, spin_black

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        # Esquerda: Feed de Vídeo (Grade 2x2)
        video_layout = QGridLayout()
        
        self.views = {}
        # FPP_LEFT (0, 0), FPP_RIGHT (0, 1)
        # DEFL_LEFT (1, 0), DEFL_RIGHT (1, 1)
        
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

        add_view('19337756', 'FPP_LEFT (19337756)', 0, 0)
        add_view('19337638', 'FPP_RIGHT (19337638)', 0, 1)
        add_view('22348163', 'DEFL_LEFT (22348163)', 1, 0)
        add_view('22348161', 'DEFL_RIGHT (22348161)', 1, 1)
        
        main_layout.addLayout(video_layout, stretch=3)

        # Direita: Controles
        control_layout = QVBoxLayout()

        self.btn_connect = QPushButton("Conectar Câmeras")
        self.btn_connect.clicked.connect(self.toggle_connection)
        control_layout.addWidget(self.btn_connect)

        # Controles FPP
        fpp_group, self.fpp_exp, self.fpp_gain, self.fpp_gamma, self.fpp_black = self.create_camera_controls('FPP')
        control_layout.addWidget(fpp_group)

        # Controles DEFL
        defl_group, self.defl_exp, self.defl_gain, self.defl_gamma, self.defl_black = self.create_camera_controls('DEFL')
        control_layout.addWidget(defl_group)

        # Configurações do Padrão ChArUco
        charuco_group = QGroupBox("Padrão ChArUco")
        charuco_form = QFormLayout()

        # Pega de um gerenciador qualquer
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
                # Set initial values for FPP
                self.cam_manager.set_exposure('FPP', self.fpp_exp.value())
                self.cam_manager.set_gain('FPP', self.fpp_gain.value())
                self.cam_manager.set_gamma('FPP', self.fpp_gamma.value())
                self.cam_manager.set_black_level('FPP', self.fpp_black.value())
                
                # Set initial values for DEFL
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

    def update_board(self):
        sq = self.spin_sq_len.value()
        mk = self.spin_mk_len.value()
        for mgr in self.cal_managers.values():
            mgr.update_board_params(sq, mk)
        QMessageBox.information(self, "Padrão Atualizado", "Dimensões do ChArUco atualizadas em todas as câmeras.")

    def update_frame(self):
        if not self.cam_manager.is_streaming:
            self.timer.stop()
            self.cam_manager.disconnect()
            self.btn_connect.setText("Conectar Câmeras")
            for view in self.views.values():
                view.clear()
            return

        frames = self.cam_manager.get_frames()
        if not frames:
            return
            
        for serial, frame in frames.items():
            if frame is None or serial not in self.views:
                continue
                
            mgr = self.cal_managers.get(serial)
            if mgr:
                processed_frame, corners, ids = mgr.process_frame(frame)
                self.last_charuco_data[serial] = (corners, ids)
                
                rgb_image = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                
                self.views[serial].set_image(q_img)

    def capture_pose(self):
        captured_any = False
        
        for serial, (corners, ids) in self.last_charuco_data.items():
            if corners is not None and len(corners) >= 4:
                mgr = self.cal_managers.get(serial)
                if mgr and mgr.add_capture(corners, ids):
                    captured_any = True
                    
        if captured_any:
            # Mostrar a contagem máxima capturada entre todas as câmeras
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
