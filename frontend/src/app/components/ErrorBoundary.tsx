import { ReactNode, Component } from "react";
import { AlertCircle } from "lucide-react";

interface Props { children: ReactNode }
interface State { hasError: boolean; error: string }

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: "" };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message };
  }

  componentDidCatch(error: Error) {
    console.error("ErrorBoundary caught:", error.message);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-slate-900 rounded-2xl p-8 border border-red-500/50 text-center">
            <AlertCircle className="w-14 h-14 mx-auto mb-4 text-red-400" />
            <h1 className="text-2xl mb-2">Something went wrong</h1>
            <p className="text-slate-400 mb-6 text-sm">{this.state.error}</p>
            <button
              onClick={() => window.location.href = "/"}
              className="bg-gradient-to-r from-blue-500 to-emerald-500 text-white px-6 py-3 rounded-xl font-medium"
            >
              Return Home
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
