type Product = {
  id: number;
  name: string;
  image_url: string;
  created_at: string;
};

async function getProducts(): Promise<Product[]> {
  const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/products`, { cache: "no-store" });
    if (!res.ok) {
      return [];
    }
    return (await res.json()) as Product[];
  } catch {
    return [];
  }
}

export default async function CatalogPage() {
  const products = await getProducts();

  return (
    <main className="page">
      <h1>Каталог</h1>
      {products.length === 0 ? (
        <p>Пока пусто.</p>
      ) : (
        <ul className="catalog">
          {products.map((product) => (
            <li key={product.id} className="card">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={product.image_url} alt={product.name} />
              <span className="name">{product.name}</span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
