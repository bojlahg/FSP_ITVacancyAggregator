import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { components } from "@/api/schema";
import { toApiError } from "@/lib/api-error";

type Schemas = components["schemas"];

export type CandidateMarket = Schemas["CandidateMarketOut"];
export type MarketSkill = Schemas["MarketSkill"];
export type MarketSuggestion = Schemas["MarketSuggestion"];

// Префикс ["candidates", "me"]: правка профиля и навыков инвалидирует и рынок
export const marketKeys = { mine: ["candidates", "me", "market"] as const };

export function useMyMarket(enabled = true) {
  return useQuery({
    queryKey: marketKeys.mine,
    enabled,
    queryFn: async () => {
      const { data, error, response } = await api.GET("/api/v1/candidates/me/market");
      if (!data) throw toApiError(response, error);
      return data;
    },
  });
}
