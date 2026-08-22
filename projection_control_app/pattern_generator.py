import numpy as np
import cv2

class PatternGenerator:
    """
    Classe responsável puramente pela lógica matemática de geração de matrizes
    de Luz Estruturada (Projeção de Franjas, Deflectometria e Gray Code).
    """

    @staticmethod
    def generate_phase_shift(width, height, period, num_steps, modulation, orientation='Vertical', gamma=1.0):
        """
        Gera uma sequência de padrões de Phase Shifting (Franjas Senoidais).
        
        Args:
            width (int): Largura da tela.
            height (int): Altura da tela.
            period (int): Período da franja em pixels.
            num_steps (int): Número de passos de fase (ex: 3, 4, 8).
            modulation (int): Amplitude da franja (0 a 255).
            orientation (str): 'Horizontal' ou 'Vertical'.
            gamma (float): Correção gama aplicada ao padrão (útil para deflectometria).
            
        Returns:
            list[np.ndarray]: Lista com N imagens (matrizes numpy) em formato uint8 (grayscale).
        """
        # Evitar divisão por zero ou modulação inválida
        period = max(1, period)
        modulation = max(0, min(255, modulation))
        amplitude = modulation / 2.0
        offset = 128.0  # Fundo médio para aproveitar o range 0-255

        # Criar base de coordenadas (mesh)
        if orientation.lower() == 'vertical':
            # Franjas verticais (variam em X)
            base_coord = np.arange(width)
            coord_2d = np.tile(base_coord, (height, 1))
        else:
            # Franjas horizontais (variam em Y)
            base_coord = np.arange(height)
            coord_2d = np.tile(base_coord, (width, 1)).T

        patterns = []
        for n in range(num_steps):
            phase_shift = (2.0 * np.pi * n) / num_steps
            
            # Cálculo do Padrão Ideal
            ideal_pattern = offset + amplitude * np.cos((2.0 * np.pi * coord_2d / period) + phase_shift)
            
            # Normalização (0 a 1) para aplicar Correção Gama
            normalized_pattern = ideal_pattern / 255.0
            
            # Aplicar Gamma (se não for 1.0)
            if gamma != 1.0 and gamma > 0:
                normalized_pattern = np.power(normalized_pattern, 1.0 / gamma)
            
            # Voltar para 0-255 e converter para inteiro uint8
            final_pattern = np.clip(normalized_pattern * 255.0, 0, 255).astype(np.uint8)
            patterns.append(final_pattern)
            
        return patterns

    @staticmethod
    def generate_gray_code(width, height, num_images, orientation='Vertical', inverse=False):
        """
        Gera uma sequência de padrões Gray Code.
        
        Args:
            width (int): Largura da tela.
            height (int): Altura da tela.
            num_images (int): Número de bits/imagens.
            orientation (str): 'Horizontal' ou 'Vertical'.
            inverse (bool): Se verdadeiro, retorna também os padrões negativos/complementares intercalados.
            
        Returns:
            list[np.ndarray]: Lista com imagens (matrizes numpy) em formato uint8 (grayscale).
        """
        if orientation.lower() == 'vertical':
            size = width
        else:
            size = height

        # Coordenadas 1D (0 até size-1)
        coords = np.arange(size, dtype=np.uint32)
        
        # Converter para Gray Code: G = B XOR (B >> 1)
        # Onde B é o valor binário ajustado para espalhar pela tela
        # Para aproveitar o número de imagens (bits), escalamos a coordenada
        # de forma que 'size' pixels sejam cobertos por 2^num_images - 1.
        max_val = (1 << num_images) - 1
        scaled_coords = np.round(coords * (max_val / max(1, size - 1))).astype(np.uint32)
        
        # Cálculo do Gray Code
        gray_coords = scaled_coords ^ (scaled_coords >> 1)

        patterns = []
        for i in range(num_images - 1, -1, -1):
            # Extrair o i-ésimo bit do código de Gray
            bit_mask = 1 << i
            bit_pattern_1d = ((gray_coords & bit_mask) != 0).astype(np.uint8) * 255
            
            # Expandir para 2D
            if orientation.lower() == 'vertical':
                pattern_2d = np.tile(bit_pattern_1d, (height, 1))
            else:
                pattern_2d = np.tile(bit_pattern_1d, (width, 1)).T
                
            patterns.append(pattern_2d)
            
            if inverse:
                # O padrão inverso é o negativo da imagem atual
                pattern_inverse_2d = 255 - pattern_2d
                patterns.append(pattern_inverse_2d)
                
        return patterns
