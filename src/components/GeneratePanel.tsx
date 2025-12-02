import type { OutputContent } from "../types";

interface Props {
  outputs: OutputContent[];
  onSelectOutput: (id: number) => void;
}

const GeneratePanel = ({ outputs, onSelectOutput }: Props) => {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="font-semibold mb-3">생성된 팟캐스트</h3>

      {outputs.length === 0 ? (
        <p className="text-sm text-gray-500">
          아직 생성된 팟캐스트가 없습니다.
        </p>
      ) : (
        <ul className="space-y-3">
          {outputs.map((o) => (
            <li
              key={o.id}
              className="border rounded-lg p-3 flex flex-col gap-2 cursor-pointer"
              onClick={() => onSelectOutput(o.id)}
            >
              <div className="flex justify-between items-center">
                <span className="font-semibold truncate">{o.title}</span>
                {o.created_at && (
                  <span className="text-xs text-gray-400">
                    {new Date(o.created_at).toLocaleString()}
                  </span>
                )}
              </div>
              <div className="text-xs text-gray-500">{o.summary}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default GeneratePanel;
