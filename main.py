import os
import time
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
import traceback

app = FastAPI(
    title="NeuroChat AI",
    description="Продвинутый AI ассистент с красивым интерфейсом",
    version="1.0.0"
)

# Конфигурация
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
DEMO_MODE = not OPENROUTER_API_KEY

if DEMO_MODE:
    print("РЕЖИМ ДЕМО: OPENROUTER_API_KEY не найден. Добавьте его в настройках venv")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Шаблоны
templates = Jinja2Templates(directory="templates")


# Эндпоинт для главной страницы
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "demo_mode": DEMO_MODE
    })


# Проверка статуса API (для sidebar)
@app.get("/api/status")
async def api_status():
    try:
        if DEMO_MODE:
            return {
                "status": "demo",
                "message": "Демо-режим: добавьте API ключ",
                "timestamp": int(time.time()),
                "model": "Недоступно"
            }

        # Быстрая проверка через models endpoint
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:
            return {
                "status": "connected",
                "message": "OpenRouter API подключен",
                "timestamp": int(time.time()),
                "model": "deepseek/deepseek-chat"
            }
        else:
            return {
                "status": "error",
                "message": f"Ошибка API: {response.status_code}",
                "timestamp": int(time.time())
            }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка подключения: {str(e)}",
            "timestamp": int(time.time())
        }


# Health check
@app.get("/api/health")
async def health():
    import sys
    return {
        "status": "online",
        "service": "NeuroChat AI",
        "timestamp": int(time.time()),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "demo_mode": DEMO_MODE,
        "has_api_key": bool(OPENROUTER_API_KEY)
    }


# Основной чат-эндпоинт
@app.post("/api/chat")
async def chat(request: Request):
    start_time = time.time()

    try:
        # Получаем данные запроса
        data = await request.json()
        message = data.get("message", "").strip()

        if not message:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Сообщение не может быть пустым"
                }
            )

        # Демо-режим
        if DEMO_MODE:
            # Имитируем ответ AI в демо-режиме
            import random
            demo_responses = [
                f"В демо-режиме. Вы написали: '{message}'. Добавьте OPENROUTER_API_KEY в настройках.",
                f"Демо: '{message}'. Для работы с DeepSeek AI нужен API ключ OpenRouter.",
                f"Сообщение получено: '{message}'. Включите полный режим, добавив API ключ."
            ]

            return {
                "success": True,
                "response": random.choice(demo_responses),
                "tokens_used": 0,
                "response_time": int((time.time() - start_time) * 1000),
                "demo": True
            }

        # Реальный вызов OpenRouter
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://neurochat-ai.onrender.com",
            "X-Title": "NeuroChat AI",
            "X-Version": "1.0.0"
        }

        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": """Ты - NeuroChat AI, продвинутый интеллектуальный помощник. 
Используй Markdown для форматирования ответов. 
Для кода используй блоки кода с указанием языка. 
Будь полезным, точным и дружелюбным. 
Отвечай на языке пользователя."""
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.7,
            "top_p": 0.9,
            "frequency_penalty": 0.1,
            "presence_penalty": 0.1
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        response_time = int((time.time() - start_time) * 1000)

        # Логируем для отладки
        print(f"OpenRouter статус: {response.status_code}")
        print(f"Время ответа: {response_time}мс")

        if response.status_code == 200:
            result = response.json()

            # Извлекаем ответ
            if "choices" in result and len(result["choices"]) > 0:
                ai_response = result["choices"][0]["message"]["content"]
                tokens_used = result.get("usage", {}).get("total_tokens", 0)

                return {
                    "success": True,
                    "response": ai_response,
                    "tokens_used": tokens_used,
                    "response_time": response_time,
                    "model": "deepseek-chat"
                }
            else:
                return {
                    "success": False,
                    "error": "Некорректный ответ от API",
                    "details": str(result)[:200],
                    "response_time": response_time
                }
        else:
            # Пробуем извлечь детали ошибки
            error_details = "Неизвестная ошибка"
            try:
                error_data = response.json()
                error_details = error_data.get("error", {}).get("message", str(error_data))
            except:
                error_details = response.text[:200]

            return JSONResponse(
                status_code=response.status_code,
                content={
                    "success": False,
                    "error": f"Ошибка API ({response.status_code})",
                    "details": error_details,
                    "response_time": response_time
                }
            )

    except requests.exceptions.Timeout:
        return JSONResponse(
            status_code=504,
            content={
                "success": False,
                "error": "Таймаут соединения с OpenAI (30 сек)",
                "response_time": int((time.time() - start_time) * 1000)
            }
        )
    except requests.exceptions.ConnectionError:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": "Ошибка подключения к сети",
                "response_time": int((time.time() - start_time) * 1000)
            }
        )
    except Exception as e:
        print(f"Внутренняя ошибка сервера: {str(e)}")
        print(traceback.format_exc())

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Внутренняя ошибка сервера: {str(e)[:100]}",
                "response_time": int((time.time() - start_time) * 1000)
            }
        )


# Тестовый эндпоинт
@app.get("/api/test")
async def test_endpoint():
    return {
        "success": True,
        "message": "NeuroChat AI API работает!",
        "timestamp": int(time.time()),
        "endpoints": {
            "/": "Главная страница",
            "/api/status": "Статус подключения",
            "/api/health": "Состояние сервера",
            "/api/chat": "Чат с AI (POST)",
            "/api/test": "Тестовый эндпоинт"
        }
    }


# Эндпоинт для информации о моделях
@app.get("/api/models")
async def get_models():
    if DEMO_MODE:
        return {
            "success": False,
            "error": "Требуется API ключ",
            "demo": True
        }

    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            models = response.json()
            # Фильтруем только DeepSeek модели
            deepseek_models = [
                model for model in models.get("data", [])
                if "deepseek" in model.get("id", "").lower()
            ]

            return {
                "success": True,
                "count": len(deepseek_models),
                "models": deepseek_models[:10]  # Первые 10
            }
        else:
            return {
                "success": False,
                "error": f"Ошибка: {response.status_code}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Обработчик 404
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": f"Эндпоинт {request.url.path} не найден",
            "available_endpoints": [
                "/",
                "/api/status",
                "/api/health",
                "/api/chat",
                "/api/test",
                "/api/models"
            ]
        }
    )


# Запуск сервера
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    print("\n" + "=" * 60)
    print("NeuroChat AI Backend")
    print("=" * 60)
    print(f"Порт: {port}")
    print(f"API ключ: {'Установлен' if OPENROUTER_API_KEY else 'Не установлен (демо-режим)'}")
    print(f"Демо-режим: {'ВКЛ' if DEMO_MODE else 'ВЫКЛ'}")
    print("=" * 60)
    print(f"Сервер запущен: http://localhost:{port}")
    print(f"API статус: http://localhost:{port}/api/status")
    print(f"Документация: http://localhost:{port}/docs")
    print("=" * 60 + "\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )