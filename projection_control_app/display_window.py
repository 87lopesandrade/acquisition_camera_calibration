import numpy as np
import cv2
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt

class DisplayWindow(QWidget):
    """
    Janela sem bordas (Fullscreen) que roda no projetor ou monitor secundário
    para exibir as matrizes em tempo real.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Projection Display")
        
        # Sem bordas para não atrapalhar a calibração
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # Fundo preto
        self.setStyleSheet("background-color: black;")
        
        # Layout e Label da imagem
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.image_label)
        
        self.current_screen = None

    def move_to_screen(self, screen):
        """
        Move a janela para a tela selecionada e entra em FullScreen.
        
        Args:
            screen (QScreen): O objeto de tela onde a janela deve ser exibida.
        """
        if screen is None:
            return
            
        self.current_screen = screen
        
        # Move a janela para a geometria da tela e maximiza
        self.setGeometry(screen.geometry())
        self.showFullScreen()
        
        # Limpar o display sempre que mudar de tela
        self.clear_display()

    def get_screen_resolution(self):
        """
        Retorna a resolução (largura, altura) da tela atual.
        """
        if self.current_screen:
            rect = self.current_screen.geometry()
            return rect.width(), rect.height()
        return 1920, 1080 # Fallback

    def display_pattern(self, pattern_array):
        """
        Converte uma matriz numpy e a exibe na tela.
        
        Args:
            pattern_array (np.ndarray): Imagem (uint8, escala de cinza).
        """
        if pattern_array is None:
            return
            
        h, w = pattern_array.shape
        # Array (W, H) Grayscale para QImage
        q_img = QImage(pattern_array.data, w, h, w, QImage.Format_Grayscale8)
        pixmap = QPixmap.fromImage(q_img)
        self.image_label.setPixmap(pixmap)

    def clear_display(self):
        """
        Limpa a tela (deixa preta).
        """
        if self.current_screen:
            w, h = self.get_screen_resolution()
            black_image = np.zeros((h, w), dtype=np.uint8)
            self.display_pattern(black_image)

    def keyPressEvent(self, event):
        """
        Pressionar ESC fecha o FullScreen de emergência.
        """
        if event.key() == Qt.Key_Escape:
            self.hide()
