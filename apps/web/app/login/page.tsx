"use client";

import * as React from "react";
import { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { authService } from "@/lib/api/services";
import { toApiError } from "@/lib/api/client";
import { queryKeys } from "@/lib/query-keys";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const dynamic = "force-dynamic";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const next = searchParams.get("next") || "/jobs";

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  const login = useMutation({
    mutationFn: (values: FormValues) => authService.login(values),
    onSuccess: (me) => {
      queryClient.setQueryData(queryKeys.me, me);
      toast.success(`Welcome back, ${me.name || me.email}`);
      router.replace(next.startsWith("/") ? next : "/jobs");
    },
    onError: async (err) => {
      const e = await toApiError(err);
      toast.error(
        e.status === 401 ? "Invalid email or password." : e.message,
      );
    },
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-white px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-semibold tracking-tight text-coffee-900">
            The Outreach Desk
          </h1>
          <p className="mt-2 text-coffee-500">
            Sign in to your application engine.
          </p>
        </div>

        <div className="rounded-lg border border-coffee-300 bg-white px-8 py-8">
          <form
            onSubmit={handleSubmit((v) => login.mutate(v))}
            className="space-y-5"
            noValidate
          >
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@company.com"
                {...register("email")}
              />
              {errors.email && (
                <p className="text-sm text-status-rejected">
                  {errors.email.message}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                {...register("password")}
              />
              {errors.password && (
                <p className="text-sm text-status-rejected">
                  {errors.password.message}
                </p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full"
              size="lg"
              disabled={login.isPending}
            >
              {login.isPending ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-coffee-500">
          Have an invite?{" "}
          <Link href="/signup" className="font-medium text-coffee-900 underline">
            Create your account
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-white text-coffee-500">
          Loading…
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
