import { ChevronLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";

const BackButton = () => {
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(-1)}
      className="mb-4 text-foreground hover:text-muted-foreground transition-colors"
      aria-label="Go back"
    >
      <ChevronLeft className="w-6 h-6" />
    </button>
  );
};

export default BackButton;
