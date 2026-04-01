from aitonomos.backend.database import SessionLocal, Usuario
db = SessionLocal()
users = db.query(Usuario).all()
for u in users:
    print(f"User ID: {u.id}, Name: {u.nombre}")
    
    # Try calling the endpoint function directly to see if it crashes
    from main import get_profile
    import asyncio
    try:
        res = asyncio.run(get_profile(str(u.id), db))
        print("Success:", res)
    except Exception as e:
        print("ERROR:", str(e))
