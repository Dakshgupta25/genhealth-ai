/**
 * GenHealth AI — Family Module
 *
 * Handles family tree data management and UI interaction.
 */

const Family = (() => {
  const { family } = window.GenHealthAPI;

  let _members = [];
  let _tree = null;

  /** Fetch and cache all family members. */
  async function loadMembers() {
    _members = await family.listMembers();
    return _members;
  }

  /** Get the cached member list (call loadMembers first). */
  function getMembers() { return _members; }

  /** Add a family member and refresh cache. */
  async function addMember(data) {
    const member = await family.addMember(data);
    _members.push(member);
    return member;
  }

  /** Update a family member and refresh cache. */
  async function updateMember(id, data) {
    const updated = await family.updateMember(id, data);
    _members = _members.map((m) => (m.id === id ? updated : m));
    return updated;
  }

  /** Delete a family member from the cache. */
  async function deleteMember(id) {
    await family.deleteMember(id);
    _members = _members.filter((m) => m.id !== id);
  }

  /** Send an invite to a family member. */
  async function sendInvite(memberId, email = null, phone = null) {
    return family.sendInvite({
      family_member_id: memberId,
      invitee_email: email,
      invitee_phone: phone,
    });
  }

  /** Fetch the full family tree for SVG rendering. */
  async function loadTree() {
    _tree = await family.getTree();
    return _tree;
  }

  /** Get cached tree. */
  function getTree() { return _tree; }

  /** Fetch hereditary disease patterns. */
  async function getSharedRisks() {
    return family.getSharedRisks();
  }

  /**
   * Build a display label for a relationship string.
   * @param {string} rel - e.g. "paternal_grandfather"
   * @returns {string}   - e.g. "Paternal Grandfather"
   */
  function formatRelationship(rel) {
    return rel
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }

  /**
   * Get a risk badge color class based on risk level.
   * @param {'low'|'moderate'|'high'} level
   */
  function riskColor(level) {
    return { low: "#22C55E", moderate: "#F59E0B", high: "#EF4444" }[level] || "#64748B";
  }

  return {
    loadMembers, getMembers, addMember, updateMember, deleteMember,
    sendInvite, loadTree, getTree, getSharedRisks,
    formatRelationship, riskColor,
  };
})();

window.Family = Family;
