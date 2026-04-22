import re

with open('backend/main.py', 'r') as f:
    py = f.read()

single_presu = """
@app.get("/api/presupuestos/{user_id}/{presupuesto_id}")
async def get_presupuesto(user_id: str, presupuesto_id: str, db: Session = Depends(get_db)):
    p = db.query(Presupuesto).filter(Presupuesto.id == presupuesto_id, Presupuesto.usuario_id == user_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="No encontrado")
    return {
        "id": str(p.id),
        "client_id": str(p.cliente_id),
        "codigo_presupuesto": p.codigo_presupuesto,
        "date": p.fecha_expedicion.isoformat(),
        "due_date": p.fecha_vencimiento.isoformat() if p.fecha_vencimiento else None,
        "items": p.json_lineas,
        "amount": p.importe_total,
        "status": p.estado
    }

@app.post("/api/presupuestos")
"""

py = py.replace('@app.post("/api/presupuestos")', single_presu)

with open('backend/main.py', 'w') as f:
    f.write(py)
