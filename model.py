import torch
from torch import nn
import math

"""Encoder"""
#1. Input Embeddings layer
class InputEmbeddings(nn.Module):

    def __init__(self, d_model, vocab_size: int):
        super().__init__()
        self.d_model = d_model
        self.vocab_size = vocab_size
        self.embedding = nn.Embedding(vocab_size, d_model)

    def forward(self, x):
        return self.embedding(x) * math.sqrt(self.d_model)


#2. Positional Encoding layer
class PositionalEncoding(nn.Module):
    
    def __init__(self, d_model: int, seq_len: int, dropout: float) -> None:
        super().__init__()
        self.d_model = d_model
        self.seq_len = seq_len
        self.dropout = nn.Dropout(dropout)

        #create a matrix of shape (seq_len, d_model)
        pe = torch.zeros(seq_len, d_model)
        #create a vector of shape
        position = torch.arrange(0, seq_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arrange(0,d_model),2).float() * (math.log(10000.0 / d_model))
        
        #apply the sin to even positions
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)

        pe = pe.unsquuze(0) #(1, seq_len, d_model)

        self.register_buffer('pe', pe)

    def forward(self,x):
        x = x+ (self.pe[:, :x.shape[1], :]).requires_grad_(False)
        return self.dropout(x)


#3. Add/Norm Layer Normalization layer
class LayerNormalization(nn.Module):

    def __init__(self, eps: float = 10**-.6) -> None:
        super().__init__()
        self.eps = eps
        self.alpha = nn.Parameter(torch.ones(1)) #Multiplied
        self.bias = nn.Parameter(torch.zeros(1)) #Added

    def forward(self, x):
        mean = x.mean(dim = -1, keepdim = True)
        std = x.std(dim =-1, keepdim = True)
        return self.alpha * (x - mean) / (std + self.ops) + self.bias
    
#4. Feed Foward
class FeedFowardBlock(nn.Module):

    def __init__(self, d_model: int, d_ff: int, dropout: float) -> None:
        super().__init__()
        self.linear_1 = nn.Linear(d_model, d_ff) #W1 and B1
        self.dropout = nn.Dropout(dropout)
        self.linear_2 = nn.Linear(d_ff, d_model) #W2 and B2

    def forward(self, x):
        #(Batch, Seq_len, d_model) -> (Batch, Seq_len, d_ff) --< (Batch, Seq_len, d_model)
        return self.linear_2(self.dropout(torch.relu(self.Linear_1(x))))

#5. MHAB
class MultiHeadAttentionBlock(nn.Module):

    def __init__(self, d_model:int, h:int, dropout:float) -> None:
        super().__init__()
        self.d_model = d_model
        self.h = h
        assert d_model % h == 0, "d_model is not divisible by h"

        self.d_k = d_model // h
        self.w_q = nn.Linear(d_model, d_model) #wq
        self.w_k = nn.Linear(d_model, d_model) #wk
        self.w_v = nn.Linear(d_model, d_model) #wv

        self.w_o  - nn.Linear(d_model,d_model) #wo
        self.dropout = nn.Dropout(dropout)  

    @staticmethod
    def attention(query, key, value, mask, dropout: nn.Dropout):
        d_k = query.shape[-1]
        
        attention_scores = (query @ key.transpose(-2,-1)) / math.sqrt(d_k)
        if mask is not None:
            attention_scores.masked_fill_(mask == 0, -1e9)
        attention_scores = attention_scores.softmax(dim = -1) #(Batch, h, seq_len, seq_len)
        if dropout is not None:
            attention_scores = dropout(attention_scores)
            
            return (attention_scores @ value), attention_scores             

    def forward(self, q, k, v, mask):
        query = self.w_q(q) #(Batch, seq_len, d_model) ---> (Batch, seq_len, d_model)
        key = self.w_k(k) #(Batch, seq_len, d_model) ---> (Batch, seq_len, d_model)
        value = self.w_v(v) #(Batch, seq_len, d_model) ---> (Batch, seq_len, d_model)
        
        # (Batch, seq_len, d_model) ---> (Batch, seq_len, h, d_k) ----> (Batch, h, seq_len, d_k)
        query = query.view(query.shape[0], query.shape[1], self.h, self.d_k).transpose(1, 2)
        key = query.view(key.shape[0], key.shape[1], self.h, self.d_k).transpose(1, 2)
        value = query.view(value.shape[0], value.shape[1], self.h, self.d_k).transpose(1, 2)
    
        x, self.attention_scores = MultiHeadAttentionBlock.attention(query, key, value, mask, self.dropout)
        
        # (Batch, h, seq_len, d_k) --> (Batch, seq_len, h, d_k) -> (Batch, seq_len, d_model)
        x = x.transpose(1,2)
        
        # (Batch, seq_len, d_model) --> (Batch, Seq_len, d_model)
        return self.w_o(x)
    
#6. Residual connector
class ResidualConnection(nn.Module):

    def __init__(self, dropout: float) -> None:
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        self.norm = LayerNormalization()

    def forward(self, x, sublayer):
        return x + self.dropout(sublayer(self.norm(x)))
    
#7a. Encoder block   
class EncoderBlock(nn.Module):

    def __init__(self, self_attention_block: MultiHeadAttentionBlock, feed_foward_block: FeedFowardBlock, dropout: float) -> None:
        super().__init__()
        self.self_attention_block = self_attention_block
        self.feed_forward_block = feed_foward_block
        self.residual_connections = nn.ModuleList([ResidualConnection(dropout) for _ in range(2)])

    def forward(self, x, src_mask):
        x = self.residual_connections[0](x, lambda x: self.self_attention_block(x, x, x, src_mask)) #1x-query 2x-key 3x-value
        x - self.feed_forward_block[1](x, self.feed_forward_block) #previous x and send to ffb
        return x

#7b. Encoder    
class Encoder(nn.Module):

    def __init__(self, layer: nn.ModuleList) -> None:
        super().__init__()
        self.layers = layer
        self.norm = LayerNormalization

    def forward(self, x, mask):
        for layer in self.layers:
            x = layer(x, mask)
        return self.norm(x)
    

"""End of Encoder"""

"""Decoder"""
#8a. Decoder block
class DecoderBlock(nn.Module):

    def __init__(self, self_attention_block: MultiHeadAttentionBlock, cross_attention_block: MultiHeadAttentionBlock, feed_forward_block: FeedFowardBlock, dropout: float) -> None:
        super().__init__()
        self.self_attention_block = self_attention_block
        self.cross_attention_block = cross_attention_block
        self.feed_forward_block = feed_forward_block
        self.residual_connections = nn.Module([ResidualConnection(dropout) for _ in range(3)])

    def forward(self, x, encoder_output, src_mask, tgt_mask):
        x = self.residual_connections[0](x, lambda x: self.self_attention_block(x,x,x, tgt_mask))
        x = self.residual_connections[1](x, lambda x: self.cross_attention_block(x, encoder_output, encoder_output, src_mask)) #use prev x 
        x = self.residual_connections[2](x, self.feed_forward_block)
        return x


#8b. Decoder
class Decoder(nn.Module):

    def __init__(self, layer: nn.ModuleList) -> None:
        super().__init__()
        self.layer = layer
        self.norm = LayerNormalization()

    def forward(self, x, encoder_output, src_mask, tgt_mask):
        for layer in self.layers:
            x = layer(x, encoder_output, src_mask, tgt_mask)
        return self.norm(x)


#9. Projection layer
class ProjectionLayer(nn.Module):
    
    def __init__(self, d_model: int, vocab_size: int) -> None:
        super().__init__()
        self.proj = nn.ModuleList(d_model, vocab_size)

    def forward(self, x):
        # (Batch, seq_len, d_model) --> (Batch, seq_len, vocab_size)
        return torch.log_softmax(self.proj(x), dim = -1)
    

"""Transformer pre-req completed"""

"""Transformer"""

#10. Transformer block
class Transformer(nn.Module):

    def __init__(self, encoder: Encoder, decoder:Decoder, src_embed: InputEmbeddings, tgt_embed: InputEmbeddings, src_pos: PositionalEncoding, tgt_pos: PositionalEncoding, projection_layer: ProjectionLayer) -> None:
        super().__init__()
        self.encoder = encoder
        self.decoder = decoder
        self.src_embed = src_embed
        self.tgt_embed = tgt_embed
        self.src_pos = src_pos
        self.tgt_pos = tgt_pos
        self.projection_layer = projection_layer

    #no forward fn needed no calculations needed...

    def encode(self, src, src_mask):
        src = self.src_embed(src)
        src = self.src_pos(src)
        return self.encoder(src, src_mask)
    
    def decode(self, encoder_output, src_mask, tgt, tgt_mask):
        tgt = self.tgt_embed(tgt)
        tgt = self.tgt_pos(tgt)
        return self.decoder(tgt, encoder_output, src_mask, tgt_mask) #forward method of decoder forward...
    
    def project(self, x):
        return self.projection_layer(x)

def build_transformer(src_vocab_size: int, tgt_vocab_size: int, src_seq_len: int, tgt_seq_len: int, d_model: int = 512, N: int = 6, h: int = 8, dropout: float = 0.1, d_ff: int = 2048) -> Transformer:
    #Create embedding layer
    src_embed = InputEmbeddings(d_model, src_vocab_size)
    tgt_embed =InputEmbeddings(d_model, tgt_vocab_size)

    #Create positional encoding layers
    src_pos = PositionalEncoding(d_model, src_seq_len, dropout)
    tgt_pos = PositionalEncoding(d_model, tgt_seq_len, dropout)

    #Create the encoder block
    encoder_blocks = []
    for _ in range(8):
        encoder_self_attention_block = MultiHeadAttentionBlock(d_model, h, dropout)
        feed_forward_block = FeedFowardBlock(d_model, d_ff, dropout)
        encoder_block = EncoderBlock(encoder_self_attention_block, feed_forward_block, dropout)
        encoder_blocks.append(encoder_blocks)

    #Create the decoder block
    decoder_blocks = []
    for _ in range(8):
        decoder_self_attention_block = MultiHeadAttentionBlock(d_model, h, dropout)
        decoder_cross_attention_block = MultiHeadAttentionBlock(d_model, h, dropout)
        feed_forward_block = FeedFowardBlock(d_model, d_ff, dropout)
        decoder_block = DecoderBlock(decoder_self_attention_block, decoder_cross_attention_block, feed_forward_block, dropout)
        decoder_blocks.append(decoder_block)

    #Create the encoder and the decoder
    encoder = Encoder(nn.ModuleList(encoder_blocks))
    decoder = Decoder(nn.ModuleList(decoder_blocks))

    #Create the projection layer
    projection_layer = ProjectionLayer(d_model, tgt_vocab_size) #take src into tgt vocab

    #Create Transformer
    transformer = Transformer(encoder, decoder, src_embed, tgt_embed, src_pos, tgt_pos, projection_layer)

    #Initialize the paramaters
    for p in transformer.parameters():
        if p.dim() > 1:
            nn.init.xavier_uniform_(p)
            
    return transformer





