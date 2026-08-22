import sys
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, 
    QTabWidget, QPushButton, QSlider, QSpinBox, QFormLayout, 
    QApplication, QGroupBox, QRadioButton, QCheckBox, QDoubleSpinBox,
    QMessageBox
)
from PyQt5.QtCore import Qt

from pattern_generator import PatternGenerator
from config_manager import ConfigManager
from display_window import DisplayWindow

class ProjectionGUI(QWidget):
    def __init__(self, display_window):
        super().__init__()
        self.setWindowTitle("Control Panel - Structured Light Projection")
        self.setMinimumWidth(500)
        self.display_window = display_window
        self.config_manager = ConfigManager()
        
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 1. Seleção de Tela
        screen_layout = QHBoxLayout()
        screen_layout.addWidget(QLabel("Select Output Screen:"))
        self.combo_screens = QComboBox()
        
        self.screens = QApplication.screens()
        for i, screen in enumerate(self.screens):
            name = screen.name()
            geom = screen.geometry()
            self.combo_screens.addItem(f"{name} ({geom.width()}x{geom.height()})", screen)
            
        self.combo_screens.currentIndexChanged.connect(self.change_screen)
        screen_layout.addWidget(self.combo_screens)
        main_layout.addLayout(screen_layout)
        
        # 2. Abas Principais
        self.tabs = QTabWidget()
        
        self.tab_fpp = QWidget()
        self.tab_defl = QWidget()
        self.tab_gray = QWidget()
        
        self.tabs.addTab(self.tab_fpp, "Projeção de Franjas (FPP)")
        self.tabs.addTab(self.tab_defl, "Deflectometria")
        self.tabs.addTab(self.tab_gray, "Gray Code")
        
        self.setup_fpp_tab()
        self.setup_defl_tab()
        self.setup_gray_tab()
        
        self.tabs.currentChanged.connect(self.update_projection)
        main_layout.addWidget(self.tabs)
        
        # 3. Controles Inferiores (Preview e Save)
        bottom_layout = QHBoxLayout()
        
        self.btn_preview = QPushButton("Preview Sequence (Play)")
        self.btn_preview.clicked.connect(self.play_sequence)
        
        self.btn_save = QPushButton("Salvar Parâmetros (config.json)")
        self.btn_save.clicked.connect(self.save_parameters)
        
        bottom_layout.addWidget(self.btn_preview)
        bottom_layout.addWidget(self.btn_save)
        
        main_layout.addLayout(bottom_layout)
        
        # Mover para a tela selecionada inicialmente
        self.change_screen(self.combo_screens.currentIndex())

    # --- SETUP TABS ---
    def setup_fpp_tab(self):
        layout = QFormLayout(self.tab_fpp)
        
        self.fpp_period = QSpinBox()
        self.fpp_period.setRange(8, 1024)
        self.fpp_period.setValue(64)
        self.fpp_period.valueChanged.connect(self.update_projection)
        
        self.fpp_steps = QSpinBox()
        self.fpp_steps.setRange(3, 32)
        self.fpp_steps.setValue(4)
        self.fpp_steps.valueChanged.connect(self.update_projection)
        
        self.fpp_mod = QSpinBox()
        self.fpp_mod.setRange(0, 255)
        self.fpp_mod.setValue(255)
        self.fpp_mod.valueChanged.connect(self.update_projection)
        
        self.fpp_delay = QSpinBox()
        self.fpp_delay.setRange(0, 5000)
        self.fpp_delay.setValue(100)
        self.fpp_delay.setSuffix(" ms")
        
        layout.addRow("Período da Franja (Pixels):", self.fpp_period)
        layout.addRow("Número de Passos de Fase (N):", self.fpp_steps)
        layout.addRow("Modulação (I_mod 0-255):", self.fpp_mod)
        layout.addRow("Tempo de Atraso (Delay):", self.fpp_delay)

    def setup_defl_tab(self):
        layout = QFormLayout(self.tab_defl)
        
        self.defl_orient_h = QRadioButton("Horizontal")
        self.defl_orient_v = QRadioButton("Vertical")
        self.defl_orient_h.setChecked(True)
        self.defl_orient_h.toggled.connect(self.update_projection)
        
        orient_layout = QHBoxLayout()
        orient_layout.addWidget(self.defl_orient_h)
        orient_layout.addWidget(self.defl_orient_v)
        
        self.defl_period = QSpinBox()
        self.defl_period.setRange(8, 1024)
        self.defl_period.setValue(128)
        self.defl_period.valueChanged.connect(self.update_projection)
        
        self.defl_steps = QSpinBox()
        self.defl_steps.setRange(3, 32)
        self.defl_steps.setValue(8)
        self.defl_steps.valueChanged.connect(self.update_projection)
        
        self.defl_gamma = QDoubleSpinBox()
        self.defl_gamma.setRange(0.1, 5.0)
        self.defl_gamma.setSingleStep(0.1)
        self.defl_gamma.setValue(2.2)
        self.defl_gamma.valueChanged.connect(self.update_projection)
        
        layout.addRow("Orientação:", orient_layout)
        layout.addRow("Período da Franja (Pixels):", self.defl_period)
        layout.addRow("Número de Passos de Fase (N):", self.defl_steps)
        layout.addRow("Correção Gama:", self.defl_gamma)

    def setup_gray_tab(self):
        layout = QFormLayout(self.tab_gray)
        
        self.gray_orient_h = QRadioButton("Horizontal")
        self.gray_orient_v = QRadioButton("Vertical")
        self.gray_orient_h.setChecked(True)
        self.gray_orient_h.toggled.connect(self.update_projection)
        
        orient_layout = QHBoxLayout()
        orient_layout.addWidget(self.gray_orient_h)
        orient_layout.addWidget(self.gray_orient_v)
        
        self.gray_bits = QSpinBox()
        self.gray_bits.setRange(4, 16)
        self.gray_bits.setValue(8)
        self.gray_bits.valueChanged.connect(self.update_projection)
        
        self.gray_inverse = QCheckBox("Habilitar Padrão Inverso (Complementar)")
        self.gray_inverse.setChecked(False)
        self.gray_inverse.stateChanged.connect(self.update_projection)
        
        layout.addRow("Orientação:", orient_layout)
        layout.addRow("Número de Imagens (Resolução em Bits):", self.gray_bits)
        layout.addRow("Padrão Inverso:", self.gray_inverse)

    # --- LOGIC ---
    def change_screen(self, index):
        screen = self.combo_screens.itemData(index)
        self.display_window.move_to_screen(screen)
        self.update_projection()

    def update_projection(self):
        """
        Gera e exibe apenas o primeiro frame do padrão atual em tempo real
        para o usuário visualizar os ajustes matemáticos.
        """
        w, h = self.display_window.get_screen_resolution()
        current_tab = self.tabs.currentIndex()
        
        patterns = []
        if current_tab == 0: # FPP
            patterns = PatternGenerator.generate_phase_shift(
                w, h, 
                self.fpp_period.value(), 
                self.fpp_steps.value(), 
                self.fpp_mod.value(),
                'Vertical', # FPP geralmente usa linhas verticais para reconstruir X
                gamma=1.0
            )
        elif current_tab == 1: # DEFL
            orientation = 'Horizontal' if self.defl_orient_h.isChecked() else 'Vertical'
            patterns = PatternGenerator.generate_phase_shift(
                w, h, 
                self.defl_period.value(), 
                self.defl_steps.value(), 
                255, # Modulação cheia para deflectometria geralmente
                orientation,
                gamma=self.defl_gamma.value()
            )
        elif current_tab == 2: # Gray Code
            orientation = 'Horizontal' if self.gray_orient_h.isChecked() else 'Vertical'
            patterns = PatternGenerator.generate_gray_code(
                w, h, 
                self.gray_bits.value(),
                orientation,
                self.gray_inverse.isChecked()
            )
            
        if patterns:
            # Exibe apenas a imagem 0 (preview estático)
            self.display_window.display_pattern(patterns[0])

    def play_sequence(self):
        """
        (Futuro/Opcional) Poderia iterar pela lista gerada e exibir a sequência com delay.
        """
        QMessageBox.information(self, "Preview", "Aqui a sequência completa piscaria na tela. Para o Preview atualizamos apenas o frame 0 em tempo real.")

    def save_parameters(self):
        """
        Coleta todos os dados das 3 abas estruturadamente e salva.
        """
        config_dict = {
            "fringe_projection": {
                "period_pixels": self.fpp_period.value(),
                "phase_steps": self.fpp_steps.value(),
                "modulation": self.fpp_mod.value(),
                "delay_ms": self.fpp_delay.value()
            },
            "deflectometry": {
                "orientation": "Horizontal" if self.defl_orient_h.isChecked() else "Vertical",
                "period_pixels": self.defl_period.value(),
                "phase_steps": self.defl_steps.value(),
                "gamma_correction": self.defl_gamma.value()
            },
            "gray_code": {
                "orientation": "Horizontal" if self.gray_orient_h.isChecked() else "Vertical",
                "resolution_bits": self.gray_bits.value(),
                "inverse_pattern": self.gray_inverse.isChecked()
            }
        }
        
        json_path, npy_path = self.config_manager.save_config(config_dict, "projection_config")
        
        QMessageBox.information(
            self, 
            "Sucesso", 
            f"Configurações matemáticas estruturadas salvas em:\n\n{json_path}\n{npy_path}"
        )
