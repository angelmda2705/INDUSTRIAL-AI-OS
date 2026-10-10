"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";

export const PASSWORD_HINT = "Mínimo 10 caracteres, con letras y números. Evita contraseñas comunes o tu usuario de correo.";

const schema = z
  .object({
    current: z.string().optional(),
    password: z
      .string()
      .min(10, "Debe tener al menos 10 caracteres.")
      .regex(/[A-Za-zÁÉÍÓÚáéíóúñÑ]/, "Debe incluir al menos una letra.")
      .regex(/\d/, "Debe incluir al menos un número."),
    confirm: z.string(),
  })
  .refine((v) => v.password === v.confirm, { path: ["confirm"], message: "Las contraseñas no coinciden." });

export type PasswordValues = z.infer<typeof schema>;

export function PasswordForm({ askCurrent, onSubmit, submitLabel }: {
  askCurrent?: boolean;
  onSubmit: (values: PasswordValues) => Promise<void>;
  submitLabel: string;
}) {
  const { register, handleSubmit, formState } = useForm<PasswordValues>({ resolver: zodResolver(schema) });
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      {askCurrent && (
        <Field label="Contraseña actual" htmlFor="current">
          <Input id="current" type="password" autoComplete="current-password" {...register("current")} />
        </Field>
      )}
      <Field label="Nueva contraseña" htmlFor="password" hint={PASSWORD_HINT} error={formState.errors.password?.message}>
        <Input id="password" type="password" autoComplete="new-password" {...register("password")} />
      </Field>
      <Field label="Confirma la nueva contraseña" htmlFor="confirm" error={formState.errors.confirm?.message}>
        <Input id="confirm" type="password" autoComplete="new-password" {...register("confirm")} />
      </Field>
      <Button type="submit" className="w-full" loading={formState.isSubmitting}>
        {submitLabel}
      </Button>
    </form>
  );
}
