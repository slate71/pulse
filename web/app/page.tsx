"use client";

import { useState, FormEvent } from "react";
import Head from "next/head";

export default function Home() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleEmailSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);

    // Simple form submission - replace with your preferred service
    try {
      // For now, just simulate submission
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setSubmitted(true);
      setEmail("");
    } catch (error) {
      console.error("Error submitting email:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Pulse - Never be surprised in standup again</title>
        <meta
          name="description"
          content="Know what your team is working on before standup starts. Join the beta for $29/month."
        />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <main className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
        {/* Header */}
        <header className="container mx-auto px-6 py-8">
          <div className="flex items-center justify-between">
            <div className="text-2xl font-bold text-slate-800">Pulse</div>
            <div className="text-sm text-slate-600">Coming Soon</div>
          </div>
        </header>

        {/* Hero Section */}
        <section className="container mx-auto px-6 py-16 text-center">
          <h1 className="text-5xl md:text-6xl font-bold text-slate-900 mb-6 leading-tight">
            Never be surprised in <br />
            <span className="text-blue-600">standup</span> again
          </h1>

          <p className="text-xl text-slate-600 mb-12 max-w-2xl mx-auto leading-relaxed">
            Know what your team is working on before the meeting starts. Get
            real-time updates, track progress, and make standups actually
            useful.
          </p>

          {/* Email Capture */}
          <div className="max-w-md mx-auto mb-8">
            {submitted ? (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-green-800">
                ✨ Thanks! We'll keep you updated on our progress.
              </div>
            ) : (
              <form onSubmit={handleEmailSubmit} className="flex gap-3">
                <input
                  type="email"
                  value={email}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
                  placeholder="Enter your email"
                  required
                  className="flex-1 px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="px-6 py-3 bg-slate-800 text-white rounded-lg font-medium hover:bg-slate-700 transition-colors disabled:opacity-50"
                >
                  {loading ? "..." : "Notify Me"}
                </button>
              </form>
            )}
          </div>

          {/* Beta CTA */}
          <div className="mb-16">
            <a
              href="https://buy.stripe.com/test_your_payment_link_here" // Replace with actual Stripe payment link
              className="inline-flex items-center gap-2 px-8 py-4 bg-blue-600 text-white rounded-lg font-semibold text-lg hover:bg-blue-700 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all"
            >
              🚀 Join Beta - $29/month
            </a>
            <p className="text-sm text-slate-500 mt-3">
              Early access • Cancel anytime • 30-day money back guarantee
            </p>
          </div>
        </section>

        {/* Features Preview */}
        <section className="container mx-auto px-6 py-16">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold text-slate-900 text-center mb-12">
              What makes standups better?
            </h2>

            <div className="grid md:grid-cols-3 gap-8">
              <div className="text-center">
                <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl">📊</span>
                </div>
                <h3 className="text-xl font-semibold text-slate-800 mb-2">
                  Real-time Updates
                </h3>
                <p className="text-slate-600">
                  See what everyone's working on throughout the day, not just
                  during meetings.
                </p>
              </div>

              <div className="text-center">
                <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl">⚡</span>
                </div>
                <h3 className="text-xl font-semibold text-slate-800 mb-2">
                  Faster Standups
                </h3>
                <p className="text-slate-600">
                  Come prepared with context. Spend time solving problems, not
                  catching up.
                </p>
              </div>

              <div className="text-center">
                <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl">🎯</span>
                </div>
                <h3 className="text-xl font-semibold text-slate-800 mb-2">
                  Stay Aligned
                </h3>
                <p className="text-slate-600">
                  Spot blockers early and keep everyone moving in the same
                  direction.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Social Proof / Testimonial Placeholder */}
        <section className="container mx-auto px-6 py-16">
          <div className="max-w-2xl mx-auto text-center bg-white rounded-2xl p-8 shadow-sm border border-slate-200">
            <p className="text-lg text-slate-700 italic mb-4">
              "Finally, a tool that makes our standups actually productive
              instead of just status updates."
            </p>
            <div className="text-slate-600">
              <span className="font-medium">Early Beta User</span>
              <span className="mx-2">•</span>
              <span>Engineering Manager</span>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="container mx-auto px-6 py-12 border-t border-slate-200">
          <div className="text-center text-slate-600">
            <p className="mb-4">
              Built for teams that ship fast and stay aligned.
            </p>
            <p className="text-sm">
              Questions? Email us at{" "}
              <a
                href="mailto:hello@yourpulsedomain.com"
                className="text-blue-600 hover:underline"
              >
                hello@yourpulsedomain.com
              </a>
            </p>
          </div>
        </footer>
      </main>
    </>
  );
}