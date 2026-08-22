import sys
from PyQt5.QtWidgets import QApplication
from display_window import DisplayWindow
from gui import ProjectionGUI

def main():
    app = QApplication(sys.argv)
    
    # 1. Cria a janela do projetor (sem bordas, no segundo monitor)
    display_win = DisplayWindow()
    
    # 2. Cria o Painel de Controle, passando a referência da janela de projeção
    control_win = ProjectionGUI(display_window=display_win)
    
    # 3. Exibe o Painel de Controle (a display_window é controlada por ele)
    control_win.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
