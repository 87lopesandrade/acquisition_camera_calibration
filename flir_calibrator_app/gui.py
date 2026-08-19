import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QGroupBox, QDoubleSpinBox, QFormLayout, 
                             QMessageBox, QCheckBox, QFileDialog)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
import cv2

class CalibratorGUI(QWidget):
    def __init__(self, camera_manager, calibration_manager):
        super().__init__()
        self.cam_manager = camera_manager
        self.cal_manager = calibration_manager
        
        self.setWindowTitle("FLIR Camera Calibrator - ChArUco")
        self.resize(1000, 700)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        
        self.last_charuco_corners = None
        self.last_charuco_ids = None
        self.calibration_results = None

        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        # Esquerda: Feed de Vídeo
        video_layout = QVBoxLayout()
        self.video_label = QLabel("Feed de Vídeo")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        video_layout.addWidget(self.video_label)
        main_layout.addLayout(video_layout, stretch=2)

        # Direita: Controles
        control_layout = QVBoxLayout()

        # 1. Controles da Câmera
        cam_group = QGroupBox("Controle da Câmera FLIR")
        cam_form = QFormLayout()

        self.btn_connect = QPushButton("Conectar Câmera")
        self.btn_connect.clicked.connect(self.toggle_connection)
        cam_form.addRow(self.btn_connect)

        self.spin_exposure = QDoubleSpinBox()
        self.spin_exposure.setRange(10.0, 100000.0)
        self.spin_exposure.setValue(5000.0)
        self.spin_exposure.setSingleStep(500.0)
        self.spin_exposure.valueChanged.connect(lambda v: self.cam_manager.set_exposure(v))
        cam_form.addRow("Exposure Time (us):", self.spin_exposure)

        self.spin_gain = QDoubleSpinBox()
        self.spin_gain.setRange(0.0, 40.0)
        self.spin_gain.setValue(0.0)
        self.spin_gain.setSingleStep(1.0)
        self.spin_gain.valueChanged.connect(lambda v: self.cam_manager.set_gain(v))
        cam_form.addRow("Gain (dB):", self.spin_gain)

        self.spin_gamma = QDoubleSpinBox()
        self.spin_gamma.setRange(0.1, 4.0)
        self.spin_gamma.setValue(1.0)
        self.spin_gamma.setSingleStep(0.1)
        self.spin_gamma.valueChanged.connect(lambda v: self.cam_manager.set_gamma(v))
        cam_form.addRow("Gamma:", self.spin_gamma)

        self.spin_black = QDoubleSpinBox()
        self.spin_black.setRange(0.0, 10.0)
        self.spin_black.setValue(0.0)
        self.spin_black.setSingleStep(0.1)
        self.spin_black.valueChanged.connect(lambda v: self.cam_manager.set_black_level(v))
        cam_form.addRow("Black Level (%):", self.spin_black)

        self.chk_wb_auto = QCheckBox("Auto White Balance")
        self.chk_wb_auto.stateChanged.connect(self.toggle_wb)
        cam_form.addRow("White Balance:", self.chk_wb_auto)

        cam_group.setLayout(cam_form)
        control_layout.addWidget(cam_group)

        # 2. Configurações do Padrão ChArUco
        charuco_group = QGroupBox("Padrão ChArUco (11x8 DICT_5X5_50)")
        charuco_form = QFormLayout()

        self.spin_sq_len = QDoubleSpinBox()
        self.spin_sq_len.setDecimals(3)
        self.spin_sq_len.setRange(0.001, 1.000)
        self.spin_sq_len.setValue(self.cal_manager.square_length)
        self.spin_sq_len.setSingleStep(0.001)

        self.spin_mk_len = QDoubleSpinBox()
        self.spin_mk_len.setDecimals(3)
        self.spin_mk_len.setRange(0.001, 1.000)
        self.spin_mk_len.setValue(self.cal_manager.marker_length)
        self.spin_mk_len.setSingleStep(0.001)

        self.btn_update_board = QPushButton("Atualizar Padrão")
        self.btn_update_board.clicked.connect(self.update_board)

        charuco_form.addRow("Square Length (m):", self.spin_sq_len)
        charuco_form.addRow("Marker Length (m):", self.spin_mk_len)
        charuco_form.addRow(self.btn_update_board)
        
        charuco_group.setLayout(charuco_form)
        control_layout.addWidget(charuco_group)

        # 3. Controles de Calibração
        calib_group = QGroupBox("Ações de Calibração")
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

        self.btn_save = QPushButton("Salvar Parâmetros (.npy / .json)")
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
                self.cam_manager.start_stream()
                self.timer.start(30) # ~33 FPS
                self.btn_connect.setText("Desconectar Câmera")
                
                # Seta os valores iniciais na camera
                self.cam_manager.set_exposure(self.spin_exposure.value())
                self.cam_manager.set_gain(self.spin_gain.value())
                self.cam_manager.set_gamma(self.spin_gamma.value())
                self.cam_manager.set_black_level(self.spin_black.value())
            else:
                QMessageBox.critical(self, "Erro", msg)
        else:
            self.timer.stop()
            self.cam_manager.disconnect()
            self.btn_connect.setText("Conectar Câmera")
            self.video_label.clear()
            self.video_label.setText("Feed de Vídeo")

    def toggle_wb(self, state):
        enable = (state == Qt.Checked)
        self.cam_manager.set_white_balance_auto(enable)

    def update_board(self):
        sq = self.spin_sq_len.value()
        mk = self.spin_mk_len.value()
        self.cal_manager.update_board_params(sq, mk)
        QMessageBox.information(self, "Padrão Atualizado", "As dimensões do ChArUco foram atualizadas.")

    def update_frame(self):
        frame = self.cam_manager.get_frame()
        if frame is not None:
            processed_frame, corners, ids = self.cal_manager.process_frame(frame)
            self.last_charuco_corners = corners
            self.last_charuco_ids = ids
            
            # Converter BGR para RGB para o QImage
            rgb_image = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            q_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # Exibir mantendo a proporção
            pixmap = QPixmap.fromImage(q_img)
            self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def capture_pose(self):
        if self.last_charuco_corners is not None and len(self.last_charuco_corners) >= 4:
            if self.cal_manager.add_capture(self.last_charuco_corners, self.last_charuco_ids):
                count = len(self.cal_manager.all_corners)
                self.lbl_poses.setText(f"Poses capturadas: {count}")
            else:
                QMessageBox.warning(self, "Aviso", "Não foi possível capturar a pose. Verifique se o tabuleiro está visível.")
        else:
            QMessageBox.warning(self, "Aviso", "Tabuleiro não detectado ou poucos cantos visíveis.")

    def clear_poses(self):
        self.cal_manager.clear_captures()
        self.lbl_poses.setText("Poses capturadas: 0")
        self.calibration_results = None
        self.btn_save.setEnabled(False)

    def run_calibration(self):
        success, result = self.cal_manager.calibrate()
        if success:
            self.calibration_results = result
            rms = result["rms"]
            self.btn_save.setEnabled(True)
            QMessageBox.information(self, "Calibração Concluída", f"Calibração realizada com sucesso!\nErro de Reprojeção (RMS): {rms:.4f}")
        else:
            QMessageBox.critical(self, "Erro na Calibração", result)

    def save_params(self):
        if self.calibration_results:
            dir_path = QFileDialog.getExistingDirectory(self, "Selecionar pasta para salvar", ".")
            if dir_path:
                try:
                    path = self.cal_manager.save_calibration(self.calibration_results, dir_path)
                    QMessageBox.information(self, "Sucesso", f"Parâmetros salvos em:\n{dir_path}\n(Arquivos .npy e .json)")
                except Exception as e:
                    QMessageBox.critical(self, "Erro", f"Erro ao salvar: {str(e)}")

    def closeEvent(self, event):
        self.cam_manager.disconnect()
        event.accept()
