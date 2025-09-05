import { Redis } from "@upstash/redis";
import { Resend } from "resend";
import { NextResponse } from "next/server";

// Initialize Redis client
const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

// Initialize Resend client
const resend = new Resend(process.env.RESEND_API_KEY);

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

    // Send notification email
    try {
      await resend.emails.send({
        from: "Pulse Waitlist <onboarding@resend.dev>", // Use resend.dev for now
        to: process.env.NOTIFICATION_EMAIL || "your@email.com",
        subject: "New Pulse waitlist signup",
        html: `
          <h2>New Pulse Waitlist Signup</h2>
          <p><strong>Email:</strong> ${email}</p>
          <p><strong>Time:</strong> ${timestamp}</p>
          <hr>
          <p>🎉 Another soul saved from engineering chaos! They're ready to turn their daily madness into three beautiful, actionable items.</p>
        `,
      });
    } catch (emailError) {
      console.error("Failed to send notification email:", emailError);
      // Don't fail the signup if email fails
    }

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