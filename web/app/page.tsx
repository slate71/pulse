"use client";

import React, { useState, FormEvent } from "react";
import Head from "next/head";

export default function Home() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleEmailSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/subscribe", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email }),
      });

      const data = await response.json();

      if (response.ok) {
        setSubmitted(true);
        setEmail("");
      } else {
        setError(data.error || "Something went wrong");
      }
    } catch (error) {
      console.error("Error submitting email:", error);
      setError("Failed to connect. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Pulse - Transform engineering chaos into daily actions</title>
        <meta
          name="description"
          content="Transform engineering chaos into daily actions. Never miss what matters."
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
            Transform engineering chaos <br />
            into <span className="text-blue-600">daily action</span>
          </h1>

          <p className="text-xl text-slate-600 mb-12 max-w-2xl mx-auto leading-relaxed">
            Cut through the noise of PRs, tickets, and blockers. Get AI-powered
            insights that tell you exactly what needs your attention today.
            Never miss what matters.
          </p>

          {/* Email Capture */}
          <div className="max-w-md mx-auto mb-8">
            {submitted ? (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-green-800">
                ✨ Thanks! We'll keep you updated on our progress.
              </div>
            ) : (
              <>
                <form onSubmit={handleEmailSubmit} className="flex gap-3">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Enter your email"
                    required
                    className="flex-1 px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-slate-900"
                  />
                  <button
                    type="submit"
                    disabled={loading}
                    className="px-6 py-3 bg-slate-800 text-white rounded-lg font-medium hover:bg-slate-700 transition-colors disabled:opacity-50"
                  >
                    {loading ? "..." : "Notify Me"}
                  </button>
                </form>
                {error && (
                  <p className="mt-2 text-sm text-red-600">{error}</p>
                )}
              </>
            )}
          </div>
        </section>

        {/* Features Preview */}
        <section className="container mx-auto px-6 py-16">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-3xl font-bold text-slate-900 text-center mb-12">
              From chaos to clarity in seconds
            </h2>

            <div className="grid md:grid-cols-3 gap-8">
              <div className="text-center">
                <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl">📊</span>
                </div>
                <h3 className="text-xl font-semibold text-slate-800 mb-2">
                  AI-Powered Focus
                </h3>
                <p className="text-slate-600">
                  Analyzes PRs, tickets, and blockers to surface exactly what
                  needs attention.
                </p>
              </div>

              <div className="text-center">
                <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl">⚡</span>
                </div>
                <h3 className="text-xl font-semibold text-slate-800 mb-2">
                  Three Daily Actions
                </h3>
                <p className="text-slate-600">
                  No more endless task lists. Just three critical actions to
                  move your team forward.
                </p>
              </div>

              <div className="text-center">
                <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mx-auto mb-4">
                  <span className="text-2xl">🎯</span>
                </div>
                <h3 className="text-xl font-semibold text-slate-800 mb-2">
                  Never Miss Critical Work
                </h3>
                <p className="text-slate-600">
                  Important PRs, blocked tickets, team dependencies - nothing
                  falls through the cracks.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Social Proof / Testimonial Placeholder */}
        <section className="container mx-auto px-6 py-16">
          <div className="max-w-2xl mx-auto text-center bg-white rounded-2xl p-8 shadow-sm border border-slate-200">
            <p className="text-lg text-slate-700 italic mb-4">
              "Pulse turned our engineering chaos into clarity. We now know
              exactly what to focus on every single day."
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
              Built for engineering teams that refuse to let critical work slip
              through the cracks.
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
