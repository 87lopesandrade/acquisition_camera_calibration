# FLIR Camera Calibrator (Metrologia Óptica)

Este aplicativo foi desenvolvido para controle simultâneo, aquisição de imagem e calibração de um sistema de 4 câmeras FLIR utilizando o SDK Spinnaker (PySpin). O software é otimizado para tarefas de metrologia óptica, especificamente **Projeção de Franjas (FPP)** e **Deflectometria (DEFL)**.

## Como Iniciar

O ambiente virtual (com Python 3.10, OpenCV e a versão correta do PySpin) já foi totalmente configurado e testado. Para iniciar a interface gráfica no Mac, abra o terminal na pasta do projeto e execute:

```bash
./run_mac.sh
```

## Guia de Operação

### 1. Conexão e Controle de Câmeras
*   Clique em **"Conectar Câmeras"** para inicializar o hardware e exibir o streaming ao vivo.
*   **Grupos de Câmeras:** Para facilitar o ajuste estéreo, os controles são divididos em dois grupos independentes (FPP e DEFL).
*   **Análise de Intensidade (Evitar Saturação):**
    *   Ao ajustar a **Exposição (Exposure)** e **Ganho (Gain)**, utilize o *Slider* inferior de cada imagem para mover a **Linha Vermelha de Referência**.
    *   Os **Gráficos de Intensidade** (abaixo das imagens) mostram a curva de brilho (0-255) referente a essa linha vermelha em tempo real.
    *   **Atenção Metrológica:** O ajuste ideal para reconstrução de fase/franjas é quando o pico da curva chega o mais alto possível, mas **sem tocar no teto de 255** (para evitar saturação de pixel, o que destrói a informação do cosseno da franja).

### 2. Configuração do Padrão de Calibração
O software utiliza a detecção automática de tabuleiros **ChArUco (11x8)**. Antes de calibrar as lentes, é fundamental informar as medidas físicas reais do tabuleiro:
1.  **Square Length (mm):** Use um paquímetro para medir o tamanho do lado de um quadrado preto. Digite o valor em milímetros (ex: `30` para 30 mm).
2.  **Marker Length (mm):** Meça o tamanho do lado do marcador interno (código de barras). Digite o valor em milímetros (ex: `23` para 23 mm).
3.  Clique em **"Atualizar Padrão"**.

### 3. Calibração Intrínseca (Lentes)
A calibração intrínseca deve ser feita para descobrir a matriz da câmera (focal, centro óptico) e seus coeficientes de distorção.

1.  Posicione o tabuleiro em frente às câmeras. O software desenhará automaticamente os eixos XYZ e os contornos (em verde) quando a detecção for bem-sucedida.
2.  Mantenha o tabuleiro imóvel e clique em **"Capturar Posição Atual"**.
3.  Mova o tabuleiro para outra posição (varie a inclinação, aproxime, afaste e coloque nos 4 cantos do campo de visão) e capture novamente.
4.  Recomenda-se um mínimo de **15 a 20 poses**. O contador "Poses capturadas" na interface ajudará no acompanhamento.
5.  Clique em **"Executar Calibração"**. O cálculo matemático será executado no fundo.
6.  Se a calibração for validada e o Erro RMS for aceitável (menor que 1.0 pixel), o botão **"Salvar Parâmetros"** ficará ativo. Clique nele para gerar os arquivos `.json` e matrizes `.npy` que serão usados na futura reconstrução 3D.

### 4. Solução de Problemas Comuns
*   **Desconexão (Crash):** Ao clicar em "Desconectar", o software faz o encerramento seguro e o descarte da memória das imagens no `PySpin`. Se estiver usando hardware muito sobrecarregado, aguarde alguns segundos antes de tentar reabrir.
*   **Baixo FPS / Travamentos:** A largura de banda da porta USB é crítica quando ligamos 4 câmeras de alta resolução. O software impõe automaticamente um limite (`DeviceLinkThroughputLimit`) de ~80 MB/s por câmera. Evite usar Hubs USB não-alimentados.
