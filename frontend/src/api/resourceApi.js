import api from './axios';

const CACHE_TTL_MS = 60 * 1000;
const cache = new Map();
const pendingRequests = new Map();

async function fetchWithCacheAndDedup(key, fetcher, forceRefresh = false) {
  const now = Date.now();
  if (!forceRefresh && cache.has(key)) {
    const cached = cache.get(key);
    if (now - cached.timestamp < CACHE_TTL_MS) {
      return cached.data;
    }
  }

  if (pendingRequests.has(key)) {
    return pendingRequests.get(key);
  }

  const promise = (async () => {
    try {
      const data = await fetcher();
      cache.set(key, { data, timestamp: Date.now() });
      return data;
    } finally {
      pendingRequests.delete(key);
    }
  })();

  pendingRequests.set(key, promise);
  return promise;
}

export const resourceApi = {
  getCloudResources: async (options = {}) => {
    const { forceRefresh = false, signal } = options;
    try {
      return await fetchWithCacheAndDedup('cloud_resources', async () => {
        try {
          const response = await api.get('/api/cloud/resources', { signal });
          const items = response.data?.resources || [];
          if (items.length > 0) {
            return items.map(inst => ({
              instanceId: inst.resource_id,
              name: inst.name || inst.resource_id,
              status: inst.status === 'running' ? 'Running' : (inst.status || 'Stopped'),
              instanceType: inst.instance_type || 't3.micro',
              displayLabel: inst.display_label || `${inst.name || inst.resource_id} — ${inst.resource_id}`
            }));
          }
        } catch (err) {
          if (err?.name === 'CanceledError' || err?.name === 'AbortError') throw err;
        }
        return await resourceApi.getEc2Instances(options);
      }, forceRefresh);
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.name === 'AbortError') throw err;
      return await resourceApi.getEc2Instances(options);
    }
  },

  getCloudContext: async (resourceId = null, options = {}) => {
    const { signal } = options;
    const params = {};
    if (resourceId && resourceId.trim() && resourceId !== 'all') {
      params.resource_id = resourceId.trim();
    }
    const response = await api.get('/api/cloud/context', { params, signal });
    return response.data;
  },

  getCloudSignals: async (resourceId = null, options = {}) => {
    const { signal } = options;
    const params = {};
    if (resourceId && resourceId.trim() && resourceId !== 'all') {
      params.resource_id = resourceId.trim();
    }
    const response = await api.get('/api/cloud/signals', { params, signal });
    return response.data;
  },

  getEc2Instances: async (options = {}) => {
    const { forceRefresh = false, signal } = options;
    try {
      return await fetchWithCacheAndDedup('ec2_instances', async () => {
        const response = await api.get('/api/aws/ec2', { signal });
        const instances = response.data?.instances || [];
        return instances.map(inst => ({
          instanceId: inst.instance_id,
          name: inst.tags?.Name || inst.name || inst.instance_id,
          status: inst.state === 'running' ? 'Running' : (inst.state || 'Stopped'),
          instanceType: inst.instance_type || 't3.micro',
          cpu: inst.cpu_utilization ? `${inst.cpu_utilization}%` : 'Normal',
          az: inst.placement_az || inst.availability_zone || 'us-east-1a',
          launchTime: inst.launch_time ? new Date(inst.launch_time).toLocaleDateString() : 'Active',
          displayLabel: `${inst.tags?.Name || inst.name || inst.instance_id} — ${inst.instance_id}`
        }));
      }, forceRefresh);
    } catch (err) {
      if (err?.name === 'CanceledError' || err?.name === 'AbortError') throw err;
      console.warn('Failed to fetch EC2 instances from /api/aws/ec2', err);
      return [];
    }
  },

  getResources: async (category = 'ec2') => {
    try {
      if (category === 'ec2') {
        return await resourceApi.getEc2Instances();
      }

      if (category === 'vpc') {
        const response = await api.get('/api/aws/vpc');
        const vpcData = response.data?.vpc || {};
        const vpcs = vpcData.vpcs || [];
        const subnets = vpcData.subnets || [];
        return vpcs.map(v => ({
          vpcId: v.vpc_id,
          name: v.tags?.Name || v.name || v.vpc_id,
          cidrBlock: v.cidr_block || '10.0.0.0/16',
          subnetsCount: subnets.filter(s => s.vpc_id === v.vpc_id).length || 2,
          state: v.state || 'available',
          defaultVpc: v.is_default || false
        }));
      }

      if (category === 'securityGroups') {
        const response = await api.get('/api/aws/security-groups');
        const groups = response.data?.security_groups || [];
        return groups.map(sg => ({
          groupId: sg.group_id,
          name: sg.group_name,
          vpcId: sg.vpc_id || 'vpc-default',
          inboundRules: Array.isArray(sg.ip_permissions) ? sg.ip_permissions.length : 0,
          outboundRules: Array.isArray(sg.ip_permissions_egress) ? sg.ip_permissions_egress.length : 0,
          description: sg.description || 'Security group rule'
        }));
      }

      if (category === 'loadBalancers') {
        const response = await api.get('/api/aws/load-balancers');
        const lbs = response.data?.load_balancers || [];
        return lbs.map(alb => ({
          albName: alb.load_balancer_name || alb.name || 'app-alb',
          dnsName: alb.dns_name || 'alb-dns.amazonaws.com',
          type: alb.type || 'application',
          state: typeof alb.state === 'object' ? (alb.state?.code || 'active') : (alb.state || 'active'),
          targetGroupsCount: Array.isArray(alb.target_groups) ? alb.target_groups.length : 1,
          scheme: alb.scheme || 'internet-facing'
        }));
      }

      if (category === 'cloudWatch') {
        const response = await api.get('/api/aws/cloudwatch');
        const metrics = response.data?.metrics || [];
        return metrics.map((m, idx) => ({
          alarmName: m.metric_name || m.alarm_name || `Alarm-${idx + 1}`,
          metric: m.namespace || m.metric || 'AWS/EC2',
          threshold: m.threshold || 'CPU > 80%',
          state: m.state || 'OK',
          updatedAt: m.timestamp ? new Date(m.timestamp).toLocaleTimeString() : 'Live'
        }));
      }

      return [];
    } catch (error) {
      console.warn(`Error querying category ${category}:`, error);
      return [];
    }
  }
};

