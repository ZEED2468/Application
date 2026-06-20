"use client";

import * as React from "react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  /** render the cell for a row */
  cell: (row: T) => React.ReactNode;
  className?: string;
  headClassName?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[] | undefined;
  isLoading?: boolean;
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  emptyState?: React.ReactNode;
  skeletonRows?: number;
  /** Keep column headers visible while scrolling long tables. */
  stickyHeader?: boolean;
  /** Draw vertical rules between columns. */
  columnBorders?: boolean;
  tableClassName?: string;
}

export function DataTable<T>({
  columns,
  data,
  isLoading,
  rowKey,
  onRowClick,
  emptyState,
  skeletonRows = 6,
  stickyHeader = false,
  columnBorders = false,
  tableClassName,
}: DataTableProps<T>) {
  const cellBorder = (index: number) =>
    columnBorders && index < columns.length - 1
      ? "border-r border-coffee-200"
      : undefined;

  return (
    <Table className={tableClassName}>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          {columns.map((col, index) => (
            <TableHead
              key={col.key}
              className={cn(
                stickyHeader &&
                  "sticky top-0 z-10 bg-white shadow-[0_1px_0_0_theme(colors.coffee.300)]",
                cellBorder(index),
                col.headClassName,
              )}
            >
              {col.header}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {isLoading
          ? Array.from({ length: skeletonRows }).map((_, i) => (
              <TableRow key={`sk-${i}`} className="hover:bg-transparent">
                {columns.map((col, index) => (
                  <TableCell key={col.key} className={cellBorder(index)}>
                    <Skeleton className="h-4 w-full max-w-32" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          : (data ?? []).map((row) => (
              <TableRow
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cn(onRowClick && "cursor-pointer")}
              >
                {columns.map((col, index) => (
                  <TableCell
                    key={col.key}
                    className={cn(cellBorder(index), col.className)}
                  >
                    {col.cell(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
        {!isLoading && (data?.length ?? 0) === 0 && (
          <TableRow className="hover:bg-transparent">
            <TableCell colSpan={columns.length} className="py-12 text-center">
              {emptyState ?? (
                <span className="text-coffee-300">Nothing here yet.</span>
              )}
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
