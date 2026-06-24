/**
 * GenHealth AI — Risk Module
 *
 * Manages risk profile data and provides formatting utilities for the UI.
 */

const Risk = (() => {
  const { risk, insights } = window.GenHealthAPI;

  let _profile = null;
  let _watchlist = null;

  async function loadProfile() {
    _profile = await risk.profile();
    return _profile;
  }

  function getProfile() { return _profile; }

  async function loadWatchlist(limit = 5) {
    _watchlist = await risk.watchlist(limit);
    return _watchlist;
  }

  function getWatchlist() { return _watchlist; }

  async function triggerGeneration(force = false) {
    return risk.generate({ force });
  }

  async function getHealthScore() {
    return insights.healthScore();
  }

  async function getRecommendations() {
    return insights.recommendations();
  }

  /** @param {'low'|'moderate'|'high'} level */
  function riskLabel(level) {
    return { low: "Low Risk", moderate: "Moderate Risk", high: "High Risk" }[level] || "Unknown";
  }

  /** @param {'low'|'moderate'|'high'} level */
  function riskColor(level) {
    return { low: "#22C55E", moderate: "#F59E0B", high: "#EF4444" }[level] || "#64748B";
  }

  /** Format probability as percentage string */
  function formatPct(probability) {
    return `${Math.round(probability * 100)}%`;
  }

  return {
    loadProfile, getProfile,
    loadWatchlist, getWatchlist,
    triggerGeneration,
    getHealthScore, getRecommendations,
    riskLabel, riskColor, formatPct,
  };
})();

window.Risk = Risk;
