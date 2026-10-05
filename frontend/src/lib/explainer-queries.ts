import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";

type Schemas = components["schemas"];

export type ExplainerOverview = Schemas["ExplainerOverview"];
export type ExplainerTemplate = Schemas["ExplainerTemplate"];
export type ExplainerInstances = Schemas["ExplainerInstances"];
export type ExplainerDiversity = Schemas["ExplainerDiversity"];
export type ExplainerInformation = Schemas["ExplainerInformation"];
export type ExplainerScenario = Schemas["ExplainerScenario"];
export type ExplainerGrade = Schemas["ExplainerGrade"];
type Grade = Schemas["Grade"];

// Данные движка меняются только с деплоем: кешируем надолго, страница публичная.
const STATIC_STALE_MS = 60 * 60 * 1000;

/** Публичная страница «Как работает тест»: без входа, ключей ответов в ответах нет. */
export function useExplainerOverview() {
  return useQuery({
    queryKey: ["explainer", "overview"] as const,
    staleTime: STATIC_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/explainer/overview");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useExplainerTemplates(specialization: string | undefined) {
  return useQuery({
    queryKey: ["explainer", "templates", specialization] as const,
    enabled: Boolean(specialization),
    staleTime: STATIC_STALE_MS,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/explainer/specializations/{specialization}/templates", {
        params: { path: { specialization: specialization ?? "" } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useExplainerInstances(templateId: string | undefined, seeds: number[]) {
  return useQuery({
    queryKey: ["explainer", "instances", templateId, seeds] as const,
    enabled: Boolean(templateId) && seeds.length > 0,
    staleTime: STATIC_STALE_MS,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/explainer/templates/{template_id}/instances", {
        params: { path: { template_id: templateId ?? "" }, query: { seeds } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useExplainerDiversity(templateId: string | undefined, sample: number | undefined) {
  return useQuery({
    queryKey: ["explainer", "diversity", templateId, sample] as const,
    enabled: Boolean(templateId) && Boolean(sample),
    staleTime: STATIC_STALE_MS,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/explainer/templates/{template_id}/diversity", {
        params: { path: { template_id: templateId ?? "" }, query: { sample } },
      });
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}

export function useExplainerInformation(specialization: string | undefined, grade: Grade) {
  return useQuery({
    queryKey: ["explainer", "information", specialization, grade] as const,
    enabled: Boolean(specialization),
    staleTime: STATIC_STALE_MS,
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/api/v1/explainer/specializations/{specialization}/information",
        { params: { path: { specialization: specialization ?? "" }, query: { grade } } },
      );
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}
