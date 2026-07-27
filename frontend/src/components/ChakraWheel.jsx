export default function ChakraWheel({ className = "", spin = false, color = "currentColor" }) {
  const spokes = Array.from({ length: 24 });
  return (
    <svg
      viewBox="0 0 100 100"
      className={`${className} ${spin ? "chakra-spin" : ""}`}
      aria-hidden="true"
      role="img"
    >
      <circle cx="50" cy="50" r="46" fill="none" stroke={color} strokeWidth="4" />
      <circle cx="50" cy="50" r="7" fill={color} />
      {spokes.map((_, i) => (
        <line
          key={i}
          x1="50"
          y1="50"
          x2="50"
          y2="6"
          stroke={color}
          strokeWidth="1.6"
          transform={`rotate(${i * 15} 50 50)`}
        />
      ))}
    </svg>
  );
}
