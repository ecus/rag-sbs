# Mover y proteger el key
cp ~/Downloads/EcusSBS.pem ~/.ssh/
chmod 400 ~/.ssh/EcusSBS.pem

# Conectar (reemplaza X.X.X.X por la IP estática)
ssh -i ~/.ssh/EcusSBS.pem ubuntu@X.X.X.X