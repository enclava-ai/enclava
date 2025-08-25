import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.INTERNAL_API_URL || `http://enclava-backend:${process.env.BACKEND_INTERNAL_PORT || '8000'}` || "http://enclava-backend:8000"

export async function GET(request: NextRequest) {
  try {
    const token = request.headers.get("authorization")
    
    if (!token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const response = await fetch(`${BACKEND_URL}/api/llm/models`, {
      method: "GET",
      headers: {
        "Authorization": token,
        "Content-Type": "application/json",
      },
    })

    if (!response.ok) {
      const errorData = await response.text()
      return NextResponse.json(
        { error: "Failed to fetch models", details: errorData },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    const transformedModels = data.data?.map((model: any) => ({
      id: model.id,
      name: model.id,
      provider: model.owned_by || "unknown"
    })) || []

    return NextResponse.json({ data: transformedModels })
  } catch (error) {
    console.error("Error fetching models:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}