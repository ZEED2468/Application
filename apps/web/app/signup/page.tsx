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
  password: z.string().min(8, "At least 8 characters"),
  key: z.string().min(4, "Enter your invite key"),
});

type FormValues = z.infer<typeof schema>;

function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const invitedEmail = searchParams.get("email") ?? "";
  const invitedKey = searchParams.get("key") ?? "";
  const isVaInvite = searchParams.get("kind") === "va";

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: invitedEmail,
      password: "",
      key: invitedKey,
    },
  });

  const signup = useMutation({
    mutationFn: (values: FormValues) =>
      authService.register({
        email: values.email,
        password: values.password,
        key: values.key,
      }),
    onSuccess: (me) => {
      queryClient.setQueryData(queryKeys.me, me);
      toast.success(`Welcome, ${me.name || me.email}`);
      router.replace("/jobs");
    },
    onError: async (err) => {
      const e = await toApiError(err);
      toast.error(
        e.status === 401
          ? "That invite key or email isn't valid. Check your invite link."
          : e.message,
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
            {isVaInvite
              ? "Create your VA account from your invite."
              : "Create your account from an invite."}
          </p>
        </div>

        <div className="rounded-lg border border-coffee-300 bg-white px-8 py-8">
          <form
            onSubmit={handleSubmit((v) => signup.mutate(v))}
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
                readOnly={Boolean(invitedEmail)}
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
                autoComplete="new-password"
                placeholder="At least 8 characters"
                {...register("password")}
              />
              {errors.password && (
                <p className="text-sm text-status-rejected">
                  {errors.password.message}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="key">Invite key</Label>
              <Input
                id="key"
                type="text"
                autoCapitalize="characters"
                placeholder="6-character code"
                className="uppercase tracking-[0.3em]"
                {...register("key")}
              />
              {errors.key && (
                <p className="text-sm text-status-rejected">
                  {errors.key.message}
                </p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full"
              size="lg"
              disabled={signup.isPending}
            >
              {signup.isPending ? "Creating account…" : "Create account"}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-sm text-coffee-500">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-coffee-900 underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-white text-coffee-500">
          Loading…
        </div>
      }
    >
      <SignupForm />
    </Suspense>
  );
}
