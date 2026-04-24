export const NotificationPlugin = async ({
  client,
  $,
  directory,
}) => {
  const appleScriptString = (value) =>
    `"${String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;

  const data = (result) =>
    result?.error ? undefined : (result?.data ?? result);

  const basename = (value) => {
    const path = String(value ?? "").replace(/\/+$/, "");
    return path.split("/").pop() || path;
  };

  const state = (globalThis.__opencodeNotificationPlugin ??= {
    sessions: new Map(),
    idleAlerted: new Set(),
  });
  const sessions = state.sessions;
  const idleAlerted = state.idleAlerted;

  const rememberSession = (sessionID, info) => {
    if (!sessionID || !info) return;
    sessions.set(sessionID, {
      ...sessions.get(sessionID),
      ...info,
      id: sessionID,
    });
  };

  const eventSessionInfo = (event) => {
    const info = event.properties?.info;
    const sessionID = event.properties?.sessionID ?? info?.id;

    return { sessionID, info };
  };

  const getData = async (calls) => {
    for (const call of calls) {
      try {
        const value = data(await call());
        if (value) return value;
      } catch {}
    }
  };

  const sessionInfo = async (sessionID) => {
    const session = await getData([
      () =>
        client.session.get({
          path: { id: sessionID },
          query: { directory },
        }),
      () => client.session.get({ id: sessionID, directory }),
      () => client.session.get({ sessionID, directory }),
    ]);

    if (session) {
      rememberSession(sessionID, session);
      return session;
    }

    return sessions.get(sessionID) ?? { id: sessionID };
  };

  const branchLabel = async (sessionDirectory) => {
    const targetDirectory = sessionDirectory || directory;
    const vcs = await getData([
      () => client.vcs.get({ query: { directory: targetDirectory } }),
      () => client.vcs.get({ directory: targetDirectory }),
    ]);

    return vcs?.branch?.trim();
  };

  return {
    event: async ({ event }) => {
      const { sessionID: eventSessionID, info } = eventSessionInfo(event);

      if (event.type === "session.deleted") {
        sessions.delete(eventSessionID);
        idleAlerted.delete(eventSessionID);
        return;
      }

      rememberSession(eventSessionID, info);

      if (event.type === "session.status") {
        const status = event.properties?.status;
        if (status?.type !== "idle") {
          idleAlerted.delete(eventSessionID);
        }
        return;
      }

      if (event.type === "session.idle") {
        const sessionID = eventSessionID;
        if (!sessionID) return;

        if (idleAlerted.has(sessionID)) return;
        idleAlerted.add(sessionID);

        const session = await sessionInfo(sessionID);
        const sessionDirectory = session.directory || directory;
        const title =
          session.title?.trim() || `Session ${sessionID.slice(0, 8)}`;
        const branch = await branchLabel(sessionDirectory);
        const folder = basename(sessionDirectory);
        const message = [
          folder ? `Folder: ${folder}` : undefined,
          branch ? `Branch: ${branch}` : undefined,
        ]
          .filter(Boolean)
          .join("\n");
        const script = `display alert ${appleScriptString(title)} message ${appleScriptString(message)}`;

        await $`osascript -e ${script} > /dev/null`;
      }
    },
  };
};
