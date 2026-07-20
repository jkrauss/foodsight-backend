<script>
	import { onMount, afterUpdate } from 'svelte';
	import { user, userSettings } from './lib/stores.js';
	import axios from 'axios';

	// Chart.js is loaded via CDN in index.html — use window.Chart
	let barCanvas;
	let donutCanvas;
	let barChart;
	let donutChart;
	let data = [];
	let loading = true;

	const green = '#30974e';
	const orange = '#FFA400';

	async function loadData() {
		if (!$userSettings) return;
		try {
			const url = `/api/forecast/?store=${$userSettings.store || 1}`;
			const headers = $user?.access_token ? { Authorization: `Bearer ${$user.access_token}` } : {};
			const res = await axios.get(url, { headers });
			data = res.data;
		} catch (e) {
			try {
				const storeId = $userSettings?.store || 1;
				const res = await axios.get(`/tableDataStore${storeId}.json`);
				data = res.data;
			} catch (e2) {
				console.error('Failed to load forecast data', e2);
			}
		}
		loading = false;
	}

	function renderCharts() {
		const Chart = window.Chart;
		if (!Chart || !data.length || !barCanvas || !donutCanvas) return;

		const products = data.map(d => d.product);
		const tomorrowQty = data.map(d => d.tomorrow_order_qty);
		const dayAfterQty = data.map(d => d.day_after_order_qty);

		if (barChart) barChart.destroy();
		barChart = new Chart(barCanvas, {
			type: 'bar',
			data: {
				labels: products,
				datasets: [
					{ label: 'Morgen', data: tomorrowQty, backgroundColor: green, borderRadius: 4 },
					{ label: 'Übermorgen', data: dayAfterQty, backgroundColor: orange, borderRadius: 4 }
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				plugins: {
					legend: { position: 'top' },
					tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y} Stück` } }
				},
				scales: { y: { beginAtZero: true, title: { display: true, text: 'Stück' } } }
			}
		});

		const totalMin = data.reduce((sum, d) => {
			const m = d.tomorrow_order_range.match(/(\d+)-(\d+)/);
			return sum + (m ? parseInt(m[1]) : 0);
		}, 0);
		const totalMax = data.reduce((sum, d) => {
			const m = d.tomorrow_order_range.match(/(\d+)-(\d+)/);
			return sum + (m ? parseInt(m[2]) : 0);
		}, 0);

		if (donutChart) donutChart.destroy();
		donutChart = new Chart(donutCanvas, {
			type: 'doughnut',
			data: {
				labels: ['Bestellvorschlag', 'Sicherheitspuffer'],
				datasets: [{ data: [totalMin, totalMax - totalMin], backgroundColor: [green, orange], hoverOffset: 4 }]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				cutout: '65%',
				plugins: {
					legend: { position: 'bottom' },
					tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.parsed} Stück` } }
				}
			}
		});
	}

	$: if ($userSettings) loadData();
	$: if (data.length && barCanvas && donutCanvas) {
		// Delay chart render to next tick so canvases are in DOM
		setTimeout(renderCharts, 50);
	}
</script>

<div class="dashboard">
	<h1 class="text-2xl font-bold mb-6">Dashboard</h1>

	{#if loading}
		<div class="flex justify-center items-center h-64">
			<div class="animate-pulse text-gray-400">Lade Vorhersagedaten...</div>
		</div>
	{:else if data.length === 0}
		<div class="flex justify-center items-center h-64">
			<p class="text-gray-400">Keine Daten verfügbar. Bitte einloggen.</p>
		</div>
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
			<div class="bg-white rounded-lg shadow p-6 text-center">
				<div class="text-3xl font-bold" style="color: {green}">
					{data.reduce((s, d) => s + d.tomorrow_order_qty, 0)}
				</div>
				<div class="text-sm text-gray-500 mt-1">Stück morgen (gesamt)</div>
			</div>
			<div class="bg-white rounded-lg shadow p-6 text-center">
				<div class="text-3xl font-bold" style="color: {orange}">{data.length}</div>
				<div class="text-sm text-gray-500 mt-1">Produkte</div>
			</div>
			<div class="bg-white rounded-lg shadow p-6 text-center">
				<div class="text-3xl font-bold" style="color: {green}">7</div>
				<div class="text-sm text-gray-500 mt-1">Tage Vorhersage</div>
			</div>
		</div>

		<div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
			<div class="md:col-span-2 bg-white rounded-lg shadow p-6">
				<h2 class="text-lg font-semibold mb-4">Absatzprognose nach Produkt</h2>
				<div style="height: 300px;"><canvas bind:this={barCanvas}></canvas></div>
			</div>
			<div class="bg-white rounded-lg shadow p-6">
				<h2 class="text-lg font-semibold mb-4">Bestellbereich morgen</h2>
				<div style="height: 260px;"><canvas bind:this={donutCanvas}></canvas></div>
			</div>
		</div>

		<div class="bg-white rounded-lg shadow p-6">
			<h2 class="text-lg font-semibold mb-4">Produktdetails</h2>
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b">
							<th class="text-left py-2 px-3">Produkt</th>
							<th class="text-right py-2 px-3">Morgen</th>
							<th class="text-right py-2 px-3">Bereich</th>
							<th class="text-right py-2 px-3">Übermorgen</th>
							<th class="text-right py-2 px-3">Woche</th>
						</tr>
					</thead>
					<tbody>
						{#each data as row, i}
							<tr class="border-b hover:bg-gray-50 {i % 2 ? 'bg-gray-50/50' : ''}">
								<td class="py-2 px-3 font-medium">{row.product}</td>
								<td class="py-2 px-3 text-right font-semibold" style="color: {green}">{row.tomorrow_order_qty}</td>
								<td class="py-2 px-3 text-right text-gray-400">{row.tomorrow_order_range}</td>
								<td class="py-2 px-3 text-right">{row.day_after_order_qty}</td>
								<td class="py-2 px-3 text-right">{row.next7_order_qty}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>

<style>
	.dashboard { max-width: 1100px; margin: 0 auto; padding: 1rem; }
</style>
