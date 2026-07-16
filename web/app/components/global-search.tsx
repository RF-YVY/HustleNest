"use client";

import { Boxes, CircleAlert, Factory, FileText, Package, ReceiptText, Repeat2, Search, ShoppingBag, UserRound, X } from "lucide-react";
import { KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

export type GlobalSearchResult = {
  key: string;
  kind: "order" | "customer" | "product" | "material" | "vendor" | "expense" | "recurring" | "loss" | "document";
  title: string;
  subtitle: string;
  searchText: string;
  id: number | string;
};

const icons = { order: ShoppingBag, customer: UserRound, product: Package, material: Boxes, vendor: Factory, expense: ReceiptText, recurring: Repeat2, loss: CircleAlert, document: FileText };
const labels = { order: "Order", customer: "Customer", product: "Product", material: "Material", vendor: "Vendor", expense: "Expense", recurring: "Recurring", loss: "Loss", document: "Document" };

export function GlobalSearch({ results, onSelect }: { results: GlobalSearchResult[]; onSelect: (result: GlobalSearchResult) => void }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const matches = useMemo(() => {
    const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    return results.filter((item) => words.every((word) => item.searchText.includes(word))).slice(0, 12);
  }, [query, results]);

  useEffect(() => {
    const handleShortcut = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLocaleLowerCase() === "k") {
        event.preventDefault();
        setOpen(true);
        window.setTimeout(() => inputRef.current?.focus(), 0);
      }
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  const choose = (result: GlobalSearchResult) => {
    onSelect(result);
    setQuery("");
    setOpen(false);
    inputRef.current?.blur();
  };
  const handleKeys = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") { event.preventDefault(); setActiveIndex((value) => Math.max(0, Math.min(value + 1, matches.length - 1))); }
    if (event.key === "ArrowUp") { event.preventDefault(); setActiveIndex((value) => Math.max(value - 1, 0)); }
    if (event.key === "Enter" && matches[activeIndex]) { event.preventDefault(); choose(matches[activeIndex]); }
    if (event.key === "Escape") { setOpen(false); inputRef.current?.blur(); }
  };

  return (
    <div className="global-search-wrap" data-testid="global-search" onBlur={(event) => { if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) setOpen(false); }}>
      <label className={open ? "global-search active" : "global-search"}>
        <Search size={18} />
        <input ref={inputRef} role="combobox" aria-autocomplete="list" aria-label="Search HustleNest" aria-expanded={open} aria-controls="global-search-results" placeholder="Search orders, people, inventory, files…" value={query} onFocus={() => setOpen(true)} onChange={(event) => { setQuery(event.target.value); setActiveIndex(0); setOpen(true); }} onKeyDown={handleKeys} />
        {query ? <button type="button" aria-label="Clear search" onClick={() => { setQuery(""); inputRef.current?.focus(); }}><X size={15} /></button> : <kbd>Ctrl K</kbd>}
      </label>
      {open ? <div className="global-search-results" id="global-search-results" role="listbox">
        {!query.trim() ? <div className="search-guidance"><Search size={19} /><div><strong>Find anything in HustleNest</strong><span>Search names, order numbers, SKUs, categories, vendors, notes, or file names.</span></div></div> : matches.length ? matches.map((result, index) => {
          const Icon = icons[result.kind];
          return <button type="button" role="option" aria-selected={index === activeIndex} className={index === activeIndex ? "search-result active" : "search-result"} key={result.key} onMouseEnter={() => setActiveIndex(index)} onClick={() => choose(result)}><span className={`search-result-icon ${result.kind}`}><Icon size={17} /></span><span><strong>{result.title}</strong><small>{result.subtitle}</small></span><em>{labels[result.kind]}</em></button>;
        }) : <div className="search-guidance empty"><Search size={19} /><div><strong>No matching records</strong><span>Try fewer words or another identifier.</span></div></div>}
        {matches.length ? <div className="search-help"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>Enter</kbd> open</span><span><kbd>Esc</kbd> close</span></div> : null}
      </div> : null}
    </div>
  );
}
