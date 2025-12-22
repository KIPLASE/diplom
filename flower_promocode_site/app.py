from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import uuid
from datetime import datetime

app = FastAPI(title="Flower Promocodes")

# Создаем папки
os.makedirs("templates", exist_ok=True)

# Шаблоны
templates = Jinja2Templates(directory="templates")

# Хранилище данных (вместо БД)
users_db = {}  # username: password
promocodes_db = []  # список всех промокодов

# Счетчик ID для промокодов
next_promo_id = 1


def get_current_user(request: Request):
    """Получить текущего пользователя из cookies"""
    return request.cookies.get("username")


def is_owner(promocode, username):
    """Проверить, является ли пользователь владельцем промокода"""
    return promocode.get("owner") == username


# ========== ГЛАВНАЯ СТРАНИЦА ==========
@app.get("/")
async def home(request: Request):
    """Главная страница со всеми промокодами"""
    username = get_current_user(request)

    # Показываем ВСЕ промокоды
    return templates.TemplateResponse("index.html", {
        "request": request,
        "username": username,
        "promocodes": promocodes_db,
        "is_owner": lambda promo: is_owner(promo, username)
    })


# ========== РЕГИСТРАЦИЯ ==========
@app.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register_user(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in users_db:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Пользователь уже существует"
        })

    users_db[username] = password

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(key="username", value=username)
    return response


# ========== ВХОД ==========
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login_user(request: Request, username: str = Form(...), password: str = Form(...)):
    if username not in users_db or users_db[username] != password:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Неверное имя пользователя или пароль"
        })

    response = RedirectResponse("/", status_code=303)
    response.set_cookie(key="username", value=username)
    return response


# ========== ДОБАВЛЕНИЕ ПРОМОКОДА ==========
@app.get("/add_promo")
async def add_promo_page(request: Request):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    return templates.TemplateResponse("add_promo.html", {
        "request": request,
        "username": username
    })


@app.post("/add_promo")
async def add_promocode(request: Request,
                        code: str = Form(...),
                        shop: str = Form(...),
                        discount: str = Form(...),
                        description: str = Form(None)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    global next_promo_id

    # Создаем промокод
    promocode = {
        "id": next_promo_id,
        "code": code,
        "shop": shop,
        "discount": discount,
        "description": description or "",
        "owner": username,
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "is_active": True
    }

    promocodes_db.append(promocode)
    next_promo_id += 1

    return RedirectResponse("/", status_code=303)


# ========== РЕДАКТИРОВАНИЕ ПРОМОКОДА ==========
@app.get("/edit_promo/{promo_id}")
async def edit_promo_page(request: Request, promo_id: int):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    # Находим промокод
    promocode = next((p for p in promocodes_db if p["id"] == promo_id), None)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    # Проверяем права
    if not is_owner(promocode, username):
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "У вас нет прав для редактирования этого промокода"
        })

    return templates.TemplateResponse("edit_promo.html", {
        "request": request,
        "username": username,
        "promocode": promocode
    })


@app.post("/edit_promo/{promo_id}")
async def edit_promocode(request: Request, promo_id: int,
                         code: str = Form(...),
                         shop: str = Form(...),
                         discount: str = Form(...),
                         description: str = Form(None)):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    # Находим промокод
    promocode = next((p for p in promocodes_db if p["id"] == promo_id), None)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    # Проверяем права
    if not is_owner(promocode, username):
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "У вас нет прав для редактирования этого промокода"
        })

    # Обновляем промокод
    promocode["code"] = code
    promocode["shop"] = shop
    promocode["discount"] = discount
    promocode["description"] = description or ""

    return RedirectResponse("/", status_code=303)


# ========== УДАЛЕНИЕ ПРОМОКОДА ==========
@app.get("/delete_promo/{promo_id}")
async def delete_promocode(request: Request, promo_id: int):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    # Находим промокод
    promocode = next((p for p in promocodes_db if p["id"] == promo_id), None)
    if not promocode:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    # Проверяем права
    if not is_owner(promocode, username):
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "У вас нет прав для удаления этого промокода"
        })

    # Удаляем промокод
    promocodes_db[:] = [p for p in promocodes_db if p["id"] != promo_id]

    return RedirectResponse("/", status_code=303)


# ========== МОИ ПРОМОКОДЫ ==========
@app.get("/my_promocodes")
async def my_promocodes_page(request: Request):
    username = get_current_user(request)
    if not username:
        return RedirectResponse("/login", status_code=303)

    # Только промокоды текущего пользователя
    user_promocodes = [p for p in promocodes_db if p["owner"] == username]

    return templates.TemplateResponse("my_promocodes.html", {
        "request": request,
        "username": username,
        "promocodes": user_promocodes
    })


# ========== ВЫХОД ==========
@app.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("username")
    return response


# ========== ЗАПУСК ==========
if __name__ == "__main__":
    import uvicorn

    print("🌸 Flower Promocodes запущен!")
    print("🌐 Откройте: http://localhost:8000")

    # Добавляем тестовые данные
    if not promocodes_db:
        promocodes_db.extend([
            {
                "id": 1,
                "code": "SPRING20",
                "shop": "Цветочный рай",
                "discount": "20% на все букеты",
                "description": "Скидка на весенние букеты",
                "owner": "admin",
                "created_at": "01.03.2024 10:00",
                "is_active": True
            },
            {
                "id": 2,
                "code": "LOVE15",
                "shop": "Romantic Flowers",
                "discount": "15% на розы",
                "description": "Скидка на розы к 8 марта",
                "owner": "user1",
                "created_at": "02.03.2024 14:30",
                "is_active": True
            },
            {
                "id": 3,
                "code": "FLOWER500",
                "shop": "Flower Delivery",
                "discount": "500 руб. на первый заказ",
                "description": "Скидка для новых клиентов",
                "owner": "user2",
                "created_at": "03.03.2024 09:15",
                "is_active": True
            }
        ])
        next_promo_id = 4

    uvicorn.run(app, host="0.0.0.0", port=8000)