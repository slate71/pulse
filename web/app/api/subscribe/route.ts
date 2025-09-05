import { Redis } from "@upstash/redis";
import { NextResponse } from "next/server";

// Initialize Redis client
const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

export async function POST(request: Request) {
  try {
    const { email } = await request.json();

    if (!email || !email.includes("@")) {
      return NextResponse.json(
        { error: "Valid email required" },
        { status: 400 }
      );
    }

    // Store email with timestamp
    const timestamp = new Date().toISOString();
    const key = `waitlist:${email}`;
    
    // Check if already exists
    const existing = await redis.get(key);
    if (existing) {
      return NextResponse.json(
        { message: "Already subscribed" },
        { status: 200 }
      );
    }

    // Store in Redis
    await redis.set(key, {
      email,
      subscribedAt: timestamp,
    });

    // Also add to a list for easy retrieval
    await redis.lpush("waitlist:emails", email);

    return NextResponse.json(
      { message: "Successfully subscribed" },
      { status: 200 }
    );
  } catch (error) {
    console.error("Subscription error:", error);
    return NextResponse.json(
      { error: "Failed to subscribe" },
      { status: 500 }
    );
  }
}

// Optional: GET endpoint to retrieve count (for internal use)
export async function GET() {
  try {
    const count = await redis.llen("waitlist:emails");
    return NextResponse.json({ count });
  } catch (error) {
    return NextResponse.json({ count: 0 });
  }
}