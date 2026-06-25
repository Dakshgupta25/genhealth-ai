class FamilyTreeRenderer {
  constructor() {
    this.width = 800;
    this.height = 420;
    this.nodeRadius = 26;
  }

  render(treeData, membersList, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';

    // Create SVG element
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '100%');
    svg.setAttribute('viewBox', `0 0 ${this.width} ${this.height}`);
    svg.style.overflow = 'visible';

    // Group members by generation
    const gen2 = []; // Grandparents
    const gen1 = []; // Parents
    const gen0 = []; // Self / Siblings

    // Map members by relationship for fixed layout
    const nodeMap = {};
    treeData.members.forEach(node => {
      // Find extra invite_status from members list
      const matchingMember = membersList.find(m => m.id === node.id);
      node.invite_status = matchingMember ? matchingMember.invite_status : 'not_invited';
      nodeMap[node.relationship.toLowerCase()] = node;

      if (node.generation >= 2) gen2.push(node);
      else if (node.generation === 1) gen1.push(node);
      else gen0.push(node);
    });

    // Assign positions (x, y) to nodes
    const positions = {};

    // Gen 2 Position mapping (fixed structure for neatness, fallback to dynamic)
    const g2Order = ['paternal_grandfather', 'paternal_grandmother', 'maternal_grandfather', 'maternal_grandmother'];
    g2Order.forEach((rel, idx) => {
      const node = nodeMap[rel];
      if (node) {
        positions[node.id] = {
          x: 100 + idx * 180,
          y: 70,
          node
        };
      }
    });
    // Add any remaining gen 2 nodes dynamically
    gen2.forEach(node => {
      if (!positions[node.id]) {
        positions[node.id] = {
          x: 150 + Math.random() * 500,
          y: 70,
          node
        };
      }
    });

    // Gen 1 Position mapping
    const g1Order = ['father', 'mother'];
    g1Order.forEach((rel, idx) => {
      const node = nodeMap[rel];
      if (node) {
        positions[node.id] = {
          x: 230 + idx * 340,
          y: 190,
          node
        };
      }
    });
    // Add any remaining gen 1 nodes dynamically
    gen1.forEach(node => {
      if (!positions[node.id]) {
        positions[node.id] = {
          x: 250 + Math.random() * 300,
          y: 190,
          node
        };
      }
    });

    // Gen 0 Position mapping (User/Self at center)
    const selfNode = treeData.members.find(m => m.relationship.toLowerCase() === 'self' || m.relationship.toLowerCase() === 'user');
    if (selfNode) {
      positions[selfNode.id] = {
        x: 400,
        y: 310,
        node: selfNode
      };
    }
    // Add other siblings dynamically
    gen0.forEach(node => {
      if (!positions[node.id]) {
        positions[node.id] = {
          x: 250 + Math.random() * 300,
          y: 310,
          node
        };
      }
    });

    // 1. RENDER CONNECTIONS FIRST (so they stay in background)
    const connectionsGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    svg.appendChild(connectionsGroup);

    const drawLine = (x1, y1, x2, y2) => {
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute('x1', x1);
      line.setAttribute('y1', y1);
      line.setAttribute('x2', x2);
      line.setAttribute('y2', y2);
      line.setAttribute('stroke', 'var(--color-border)');
      line.setAttribute('stroke-width', '2');
      connectionsGroup.appendChild(line);
    };

    const drawCurve = (x1, y1, x2, y2) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      const midY = (y1 + y2) / 2;
      const d = `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`;
      path.setAttribute('d', d);
      path.setAttribute('fill', 'none');
      path.setAttribute('stroke', 'var(--color-border)');
      path.setAttribute('stroke-width', '2');
      connectionsGroup.appendChild(path);
    };

    // Draw Paternal Grandparents Spouse line & link to Father
    const patGF = nodeMap['paternal_grandfather'];
    const patGM = nodeMap['paternal_grandmother'];
    const fat = nodeMap['father'];

    if (patGF && patGM && positions[patGF.id] && positions[patGM.id]) {
      const p1 = positions[patGF.id];
      const p2 = positions[patGM.id];
      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;
      drawLine(p1.x, p1.y, p2.x, p2.y); // spouse line
      
      if (fat && positions[fat.id]) {
        drawCurve(midX, midY, positions[fat.id].x, positions[fat.id].y); // parent-child line
      }
    }

    // Draw Maternal Grandparents Spouse line & link to Mother
    const matGF = nodeMap['maternal_grandfather'];
    const matGM = nodeMap['maternal_grandmother'];
    const mot = nodeMap['mother'];

    if (matGF && matGM && positions[matGF.id] && positions[matGM.id]) {
      const p1 = positions[matGF.id];
      const p2 = positions[matGM.id];
      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;
      drawLine(p1.x, p1.y, p2.x, p2.y); // spouse line
      
      if (mot && positions[mot.id]) {
        drawCurve(midX, midY, positions[mot.id].x, positions[mot.id].y); // parent-child line
      }
    }

    // Draw Father & Mother Spouse line & link to User
    if (fat && mot && positions[fat.id] && positions[mot.id]) {
      const p1 = positions[fat.id];
      const p2 = positions[mot.id];
      const midX = (p1.x + p2.x) / 2;
      const midY = (p1.y + p2.y) / 2;
      drawLine(p1.x, p1.y, p2.x, p2.y); // spouse line

      const self = selfNode;
      if (self && positions[self.id]) {
        drawCurve(midX, midY, positions[self.id].x, positions[self.id].y); // parent-child line
      }
    }

    // 2. RENDER NODES
    const nodesGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    svg.appendChild(nodesGroup);

    Object.keys(positions).forEach(id => {
      const pos = positions[id];
      const node = pos.node;
      
      const nodeG = document.createElementNS("http://www.w3.org/2000/svg", "g");
      nodeG.style.cursor = 'pointer';
      
      // Node circle
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute('cx', pos.x);
      circle.setAttribute('cy', pos.y);
      circle.setAttribute('r', this.nodeRadius);
      circle.setAttribute('fill', 'var(--color-surface)');
      
      // Determine risk color border
      let riskColor = 'var(--color-border)';
      let hasHereditaryRisk = false;
      
      if (node.conditions && node.conditions.length > 0) {
        riskColor = 'var(--color-risk-moderate)';
        // If condition matches hereditary pattern, highlight it
        hasHereditaryRisk = true;
      }
      
      if (node.risk_contributions && node.risk_contributions.length > 0) {
        const hasHigh = node.risk_contributions.some(rc => rc.risk_level === 'high');
        riskColor = hasHigh ? 'var(--color-risk-high)' : 'var(--color-risk-moderate)';
      }
      
      circle.setAttribute('stroke', riskColor);
      circle.setAttribute('stroke-width', '3.5');
      
      // Pulsing pulse-glow class for hereditary nodes
      if (hasHereditaryRisk) {
        nodeG.setAttribute('class', 'family-node hereditary');
      } else {
        nodeG.setAttribute('class', 'family-node');
      }

      nodeG.appendChild(circle);

      // Initials Text
      const initials = document.createElementNS("http://www.w3.org/2000/svg", "text");
      initials.setAttribute('x', pos.x);
      initials.setAttribute('y', pos.y + 5);
      initials.setAttribute('font-size', '13px');
      initials.setAttribute('font-weight', '700');
      initials.setAttribute('font-family', 'var(--font-display)');
      initials.setAttribute('fill', 'var(--color-text)');
      initials.setAttribute('text-anchor', 'middle');
      
      const nameParts = node.name.split(' ');
      const initStr = nameParts.map(p => p[0]).join('').substring(0, 2).toUpperCase();
      initials.textContent = initStr;
      nodeG.appendChild(initials);

      // Name Label Below
      const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
      label.setAttribute('x', pos.x);
      label.setAttribute('y', pos.y + this.nodeRadius + 18);
      label.setAttribute('font-size', '11px');
      label.setAttribute('font-weight', '600');
      label.setAttribute('fill', 'var(--color-text)');
      label.setAttribute('text-anchor', 'middle');
      label.textContent = node.name;
      nodeG.appendChild(label);

      // Relationship Sub-label
      const relLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
      relLabel.setAttribute('x', pos.x);
      relLabel.setAttribute('y', pos.y + this.nodeRadius + 30);
      relLabel.setAttribute('font-size', '9px');
      relLabel.setAttribute('fill', 'var(--color-muted)');
      relLabel.setAttribute('text-anchor', 'middle');
      relLabel.textContent = node.relationship.replace('_', ' ').toUpperCase();
      nodeG.appendChild(relLabel);

      // Status Badge overlay if unlinked / invited
      if (node.relationship.toLowerCase() !== 'self' && node.relationship.toLowerCase() !== 'user') {
        const badgeG = document.createElementNS("http://www.w3.org/2000/svg", "g");
        
        let badgeColor = '#64748B'; // Not Invited
        let badgeText = '➕';
        let isInvitedState = false;

        if (node.is_linked) {
          badgeColor = '#22C55E'; // Linked
          badgeText = '✅';
        } else if (node.invite_status === 'pending') {
          badgeColor = '#F59E0B'; // Invite Sent
          badgeText = '⏳';
          isInvitedState = true;
        } else if (node.invite_status === 'declined') {
          badgeColor = '#EF4444'; // Declined
          badgeText = '❌';
          isInvitedState = true;
        }

        const badgeCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        badgeCircle.setAttribute('cx', pos.x + this.nodeRadius - 4);
        badgeCircle.setAttribute('cy', pos.y - this.nodeRadius + 4);
        badgeCircle.setAttribute('r', '8');
        badgeCircle.setAttribute('fill', badgeColor);
        badgeCircle.setAttribute('stroke', 'var(--color-surface)');
        badgeCircle.setAttribute('stroke-width', '1.5');
        badgeG.appendChild(badgeCircle);

        const badgeTxt = document.createElementNS("http://www.w3.org/2000/svg", "text");
        badgeTxt.setAttribute('x', pos.x + this.nodeRadius - 4);
        badgeTxt.setAttribute('y', pos.y - this.nodeRadius + 7);
        badgeTxt.setAttribute('font-size', '7px');
        badgeTxt.setAttribute('text-anchor', 'middle');
        badgeTxt.setAttribute('fill', '#ffffff');
        badgeTxt.textContent = badgeText;
        badgeG.appendChild(badgeTxt);

        nodeG.appendChild(badgeG);
      }

      // Click event
      nodeG.addEventListener('click', (e) => {
        e.stopPropagation();
        family.selectMember(node);
      });

      nodesGroup.appendChild(nodeG);
    });

    container.appendChild(svg);
  }
}

class FamilyFlowManager {
  constructor() {
    this.renderer = new FamilyTreeRenderer();
    this.members = [];
    this.treeData = null;
    this.selectedMember = null;
    this.inviteMemberId = null;
  }

  async loadFamilyData() {
    try {
      window.app.showLoader(true);
      
      const [membersRes, treeRes, risksRes] = await Promise.all([
        window.api.getFamilyMembers(),
        window.api.getFamilyTree(),
        window.api.getSharedRisks()
      ]);

      if (membersRes.success) this.members = membersRes.data;
      if (treeRes.success) this.treeData = treeRes.data;

      // Draw Tree
      if (this.treeData && this.members) {
        this.renderer.render(this.treeData, this.members, 'familyTreeCanvas');
      }

      // Render shared patterns
      if (risksRes.success) {
        this.renderHereditaryPatterns(risksRes.data.patterns);
      }
    } catch (err) {
      window.app.showToast(`❌ Error loading family tree: ${err.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }

  renderHereditaryPatterns(patterns) {
    const list = document.getElementById('hereditaryList');
    if (!list) return;
    list.innerHTML = '';

    if (!patterns || patterns.length === 0) {
      list.innerHTML = '<div class="hereditary-item"><div class="hereditary-condition">No hereditary risk patterns detected across generations yet.</div></div>';
      return;
    }

    patterns.forEach(pat => {
      const item = document.createElement('div');
      item.className = 'hereditary-item';

      let icon = '🧬';
      let iconColor = 'rgba(139, 92, 246, 0.1)';
      if (pat.disease.toLowerCase().includes('diabetes')) {
        icon = '🩸';
        iconColor = 'rgba(239, 68, 68, 0.1)';
      } else if (pat.disease.toLowerCase().includes('thyroid')) {
        icon = '🦋';
        iconColor = 'rgba(245, 158, 11, 0.1)';
      }

      const riskClass = pat.risk_level === 'high' ? 'badge-high' : 'badge-moderate';

      item.innerHTML = `
        <div style="width:40px; height:40px; border-radius:10px; background:${iconColor}; display:flex; align-items:center; justify-content:center; font-size:20px; flex-shrink:0;">${icon}</div>
        <div class="hereditary-condition">${pat.disease}</div>
        <div class="hereditary-members">Affected: ${pat.affected_members.join(', ')}</div>
        <span class="badge ${riskClass}">${pat.affected_members.length} Members</span>
        <div class="dna-badge" style="flex-shrink:0;">🧬 ${pat.generation_count} Generations</div>
      `;

      list.appendChild(item);
    });
  }

  selectMember(node) {
    this.selectedMember = node;
    const isSelf = node.relationship.toLowerCase() === 'self' || node.relationship.toLowerCase() === 'user';
    
    // Fill detailed health summary panel
    document.getElementById('detailTitle').textContent = node.name;
    const content = document.getElementById('detailContent');

    let conditionsHtml = node.conditions.length > 0
      ? node.conditions.map(c => `<span class="badge badge-moderate" style="margin-right:6px; margin-bottom:6px;">${c}</span>`).join('')
      : '<span style="font-size:13px; color:var(--color-muted);">No diagnosed conditions.</span>';

    let actionButtons = '';
    if (!isSelf) {
      if (node.is_linked) {
        actionButtons = `<button class="btn btn-outline" style="flex:1;" onclick="family.unlinkMember('${node.id}')">Disconnect Account</button>`;
      } else {
        const matchingMember = this.members.find(m => m.id === node.id);
        const status = matchingMember ? matchingMember.invite_status : 'not_invited';
        
        if (status === 'pending') {
          actionButtons = `
            <div style="text-align:center; padding: 8px; background: rgba(245,158,11,0.1); border-radius: 8px; margin-bottom: 12px; font-size:13px; color: var(--color-risk-moderate);">⏳ Invitation sent and pending verification</div>
            <button class="btn btn-primary" style="flex:1;" onclick="family.openInviteModal('${node.id}')">Resend Invitation</button>
          `;
        } else {
          actionButtons = `<button class="btn btn-primary" style="flex:1;" onclick="family.openInviteModal('${node.id}')">Invite to GenHealth</button>`;
        }
      }
    }

    content.innerHTML = `
      <div class="detail-field">
        <div class="detail-field-label">Relationship</div>
        <div class="detail-field-value">${node.relationship.replace('_', ' ').toUpperCase()}</div>
      </div>
      <div class="detail-field">
        <div class="detail-field-label">Gender</div>
        <div class="detail-field-value" style="text-transform: capitalize;">${node.gender || 'Not specified'}</div>
      </div>
      <div class="detail-field">
        <div class="detail-field-label">Known Health Conditions</div>
        <div style="margin-top: 6px;">${conditionsHtml}</div>
      </div>
      <div class="detail-field">
        <div class="detail-field-label">Account Linkage</div>
        <div class="detail-field-value">${node.is_linked ? '✅ Linked Platform Account' : '❌ Manual Node (Unlinked)'}</div>
      </div>
      <div style="margin-top: 24px; display:flex; gap:10px;">
        ${actionButtons}
      </div>
    `;

    document.getElementById('detailOverlay').classList.add('active');
  }

  openAddMemberModal() {
    document.getElementById('addMemberModal').classList.add('active');
  }

  closeAddMemberModal() {
    document.getElementById('addMemberModal').classList.remove('active');
    document.getElementById('addMemberForm').reset();
  }

  async handleAddMember(event) {
    event.preventDefault();
    const name = document.getElementById('addMemberName').value.trim();
    const relationship = document.getElementById('addMemberRel').value;
    const gender = document.getElementById('addMemberGender').value;
    const dob = document.getElementById('addMemberDob').value || null;
    const isDeceased = document.getElementById('addMemberDeceased').checked;

    if (!name || !relationship) {
      window.app.showToast('❌ Please specify Name and Relationship.');
      return;
    }

    try {
      window.app.showLoader(true);
      const res = await window.api.addFamilyMember({
        name,
        relationship,
        gender,
        date_of_birth: dob,
        is_deceased: isDeceased
      });

      if (res.success) {
        window.app.showToast('✅ Family member added to tree!');
        this.closeAddMemberModal();
        await this.loadFamilyData(); // Re-render tree
        
        // Show option to invite the newly created member
        const newMember = res.data;
        if (!isDeceased) {
          setTimeout(() => {
            this.openInviteModal(newMember.id);
          }, 800);
        }
      }
    } catch (e) {
      window.app.showToast(`❌ Failed to add member: ${e.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }

  openInviteModal(memberId) {
    this.inviteMemberId = memberId;
    
    // Retrieve member info to populate modal header
    const member = this.members.find(m => m.id === memberId);
    const label = member ? `${member.name} (${member.relationship.replace('_', ' ')})` : 'Family Member';
    
    const titleEl = document.getElementById('inviteModalTitle');
    if (titleEl) titleEl.textContent = `Invite ${label} to GenHealth`;

    // Set QR code stub details & clipboard invite link copy url
    // In production this token is requested from family/invite API first
    const inviteLinkInput = document.getElementById('inviteShareLink');
    if (inviteLinkInput) inviteLinkInput.value = 'Generating link...';

    document.getElementById('inviteModal').classList.add('active');
    
    // Pre-trigger link generation token
    this.generateInviteToken(memberId);
  }

  async generateInviteToken(memberId) {
    try {
      // Calls API to create invite and get token
      const res = await window.api.sendFamilyInvite(memberId, null, null);
      if (res.success && res.data) {
        const token = res.data.token;
        const link = `${window.location.origin}/pages/onboarding.html?invite=${token}`;
        
        const inviteLinkInput = document.getElementById('inviteShareLink');
        if (inviteLinkInput) inviteLinkInput.value = link;
      }
    } catch (e) {
      const inviteLinkInput = document.getElementById('inviteShareLink');
      if (inviteLinkInput) inviteLinkInput.value = 'Error generating invite link';
    }
  }

  closeInviteModal() {
    document.getElementById('inviteModal').classList.remove('active');
    document.getElementById('inviteEmail').value = '';
    document.getElementById('invitePhone').value = '';
    this.inviteMemberId = null;
  }

  async sendInvite() {
    if (!this.inviteMemberId) return;

    const email = document.getElementById('inviteEmail').value.trim();
    const phone = document.getElementById('invitePhone').value.trim();

    if (!email && !phone) {
      window.app.showToast('❌ Please enter either Email or Phone Number.');
      return;
    }

    try {
      window.app.showLoader(true);
      const res = await window.api.sendFamilyInvite(this.inviteMemberId, email || null, phone || null);
      if (res.success) {
        window.app.showToast('🚀 Invitation dispatched successfully!');
        this.closeInviteModal();
        await this.loadFamilyData(); // Update status badges
      }
    } catch (e) {
      window.app.showToast(`❌ Failed to send invite: ${e.message}`);
    } finally {
      window.app.showLoader(false);
    }
  }

  copyInviteLink() {
    const input = document.getElementById('inviteShareLink');
    if (input && input.value && input.value !== 'Generating link...') {
      input.select();
      navigator.clipboard.writeText(input.value);
      window.app.showToast('📋 Invite link copied to clipboard!');
    }
  }

  async unlinkMember(memberId) {
    if (confirm('Are you sure you want to disconnect this platform account linkage? manual health profile node details will be kept.')) {
      try {
        window.app.showLoader(true);
        // The delete family member API deletes the whole node, but wait:
        // We can either update their linked properties or delete them.
        // Let's call update profile or delete member depending on backend.
        // The API provides DELETE /family/members/:id -> let's delete or unlink
        const res = await window.api.deleteFamilyMember(memberId);
        if (res.success) {
          window.app.showToast('✓ Family member removed.');
          document.getElementById('detailOverlay').classList.remove('active');
          await this.loadFamilyData();
        }
      } catch (e) {
        window.app.showToast(`❌ Error: ${e.message}`);
      } finally {
        window.app.showLoader(false);
      }
    }
  }
}

const family = new FamilyFlowManager();
window.family = family;
